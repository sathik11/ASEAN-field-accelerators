import asyncio
from openai import AzureOpenAI
from promptflow.connections import CustomConnection, AzureOpenAIConnection
from promptflow.core import tool
from webresearcher import WebResearcher, Message, StepIndicator


@tool
async def my_python_tool(
    question: str,
    realtime_api_search: CustomConnection,
    aoaiConnection: AzureOpenAIConnection,
    test: bool,
    timeout: int = 120,
    filetype: str = "pdf",
):
    mesg_queue = asyncio.Queue(maxsize=100)
    list_of_messages = []

    web_researcher = WebResearcher(mesg_queue)

    if test:
        test_query = f"site:example.com filetype:{filetype} {question}"
        await mesg_queue.put(
            Message(
                content=f"Test mode enabled. Using query: {test_query}\n",
            ).model_dump_json(exclude_unset=False)
        )

    client = AzureOpenAI(
        api_key=aoaiConnection.secrets["api_key"],
        api_version="2024-05-01-preview",
        azure_endpoint=aoaiConnection.configs["api_base"],
    )
    # await mesg_queue.put(
    #     StepIndicator(
    #         title=f"Initialize",
    #         content="Web Research Assistant starting to initialize..",
    #     ).model_dump_json(exclude_unset=False)
    # )

    search_params = {"q": question, "count": 5}

    web_researcher_task = asyncio.create_task(
        web_researcher.run(search_params, realtime_api_search, filetype, client)
    )

    # Process messages from the queue
    while True:
        try:
            message = await asyncio.wait_for(mesg_queue.get(), timeout=timeout)
            list_of_messages.append(message)
            if message is None:
                break
            yield message
        except asyncio.TimeoutError:
            break
        await asyncio.sleep(0.1)

    # Wait for the web_researcher_task to finish
    await asyncio.wait_for(web_researcher_task, timeout=timeout)

    await mesg_queue.put(
        StepIndicator(
            title="Completed",
            content="Web Research Assistant has completed task.",
        ).model_dump_json(exclude_unset=False)
    )

    # Return the list of messages to the output
    yield list_of_messages
