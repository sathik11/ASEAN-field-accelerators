import asyncio

# import nest_asyncio

# nest_asyncio.apply()
import os

# from importlib.metadata import version
from promptflow.core import tool
from promptflow.connections import AzureOpenAIConnection
from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.contents.utils.author_role import AuthorRole
from semantic_kernel.kernel import Kernel
from semantic_kernel.agents.open_ai.azure_assistant_agent import AzureAssistantAgent

# nest_asyncio.apply()  # Required for Jupyter Notebooks asyncio.run() cannot be called from a running event loop

AGENT_NAME = "FileSearch"
AGENT_INSTRUCTIONS = "Find answers to the user's questions in the provided file."


# A helper method to invoke the agent with the user input
async def invoke_agent(
    mesg_queue: asyncio.Queue,
    agent: AzureAssistantAgent,
    thread_id: str,
    input: str,
    filename: str = None,
) -> None:
    """Invoke the agent with the user input."""
    await agent.add_chat_message(
        thread_id=thread_id,
        message=ChatMessageContent(role=AuthorRole.USER, content=input),
    )

    print(f"# {AuthorRole.USER}: '{input}'")

    responses = []
    async for content in agent.invoke(thread_id=thread_id):
        if content.role != AuthorRole.TOOL:
            responses.append({"role": content.role, "content": content.content})
            # print(f"# {content.role}: {content.content}")

    output = {
        "status": "success",
        "thread_id": thread_id,
        "user_input": input,
        "responses": responses,
        "message": None,  # No specific message for this output
        "filename": filename,
    }
    mesg_queue.put_nowait(output)
    return output


@tool
async def assistant_file_search(
    pdf_local_file_paths: list[str],
    pdf_remote_file_paths: list[str],
    aoaiConnection: AzureOpenAIConnection,
    timeout: int = 60,
):
    mesg_queue = asyncio.Queue()
    mesg_queue.put_nowait(
        {
            "status": "success",
            "thread_id": None,
            "user_input": None,
            "responses": [],
            "message": "### Downloading files for processing.\n"
            + "\n".join(
                [
                    f" {i + 1}. [{x.split('/')[-1]}]({x})"
                    for i, x in enumerate(pdf_remote_file_paths)
                ]
            )
            + "\n",
        }
    )

    # Create the instance of the Kernel
    kernel = Kernel()

    # Define a service_id for the sample
    service_id = "agent"
    agent = await AzureAssistantAgent.create(
        kernel=kernel,
        service_id=service_id,
        name=AGENT_NAME,
        instructions=AGENT_INSTRUCTIONS,
        enable_file_search=True,
        vector_store_filenames=pdf_local_file_paths,
        deployment_name="gpt-4o",
        api_version="2024-05-01-preview",
        endpoint=aoaiConnection.configs["api_base"],
        api_key=aoaiConnection.secrets["api_key"],
    )
    # Define a thread and invoke the agent with the user input
    thread_id = await agent.create_thread()
    mesg_queue.put_nowait(
        {
            "status": "success",
            "thread_id": None,
            "user_input": None,
            "responses": [],
            "message": "### Setting up agents to process PDF files.\n",
        }
    )

    # sleep for 5 seconds to allow the agent to be ready
    await asyncio.sleep(5)

    # create tasks
    async def process_files():
        for pdf_file in pdf_local_file_paths:
            input_text = f"Summarize contents of {os.path.basename(pdf_file)}"
            await invoke_agent(
                mesg_queue=mesg_queue,
                agent=agent,
                thread_id=thread_id,
                input=input_text,
                filename=pdf_file,
            )
        mesg_queue.put_nowait(None)  # Send None to the queue to signal completion

    # Create a task to process files
    process_task = asyncio.create_task(process_files())

    # Wait for the agent to finish processing the messages
    while True:
        try:
            message = await asyncio.wait_for(mesg_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            break
        await asyncio.sleep(
            0.1
        )  # Sleep for a short time to allow the agent to process the message
        if message is None:
            # The queue is empty, break the loop and delete the agent and thread
            [await agent.delete_file(file_id) for file_id in agent.file_search_file_ids]
            await agent.delete_thread(thread_id)
            await agent.delete()
            break
        yield message

    # Ensure the process task is completed
    await process_task

    yield {
        "status": "success",
        "thread_id": thread_id,
        "user_input": None,
        "responses": [],
        "message": "### Finished processing the files.\n",
    }
