import aiohttp
import asyncio
from promptflow.core import tool
from promptflow.connections import CustomConnection, AzureOpenAIConnection
from promptflow.tracing import trace
from tenacity import retry, stop_after_attempt, wait_random_exponential
import re
import uuid
from urllib.parse import urlparse
import tempfile
import os
from openai import AssistantEventHandler, AzureOpenAI
from typing_extensions import override
from pydantic import BaseModel, Field
from enum import Enum
import logging
import tldextract

logging.basicConfig(level=logging.INFO)


class StatusEnum(str, Enum):
    success = "success"
    error = "error"
    in_progress = "in_progress"


class Message(BaseModel):
    status: StatusEnum
    message: str
    details: dict = Field(default_factory=dict)


@trace
async def extract_domain_and_query(query: str):
    url_pattern = r"(https?://[^\s]+|www\.[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"
    url_match = re.search(url_pattern, query)

    if url_match:
        possible_url = url_match.group(0)
        query_text = query.replace(possible_url, "").strip()
        if not possible_url.startswith("http"):
            possible_url = "http://" + possible_url
        extracted_domain = tldextract.extract(possible_url)
        domain = f"{extracted_domain.domain}.{extracted_domain.suffix}"
        return domain, query_text
    else:
        return None, query


@trace
@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
async def search_bing_return_pdf_links(
    session: aiohttp.ClientSession,
    query_params: dict,
    bingConnection: CustomConnection,
    file_type="pdf",
) -> list[str]:
    BING_API_KEY = bingConnection.secrets["key"]
    headers = {"Ocp-Apim-Subscription-Key": BING_API_KEY}
    query = query_params["q"]
    domain, query_text = await extract_domain_and_query(query)

    if not domain:
        logging.error("No domain found in the query.")
        raise ValueError("No valid domain found in the search query.")

    async with session.get(
        url="https://api.bing.microsoft.com/v7.0/search",
        params={
            "q": f"site:{domain} filetype:{file_type} {query_text}",
            "count": query_params.get("count", 10),
        },
        headers=headers,
    ) as response:
        response.raise_for_status()
        search_results = await response.json()
        return [result["url"] for result in search_results["webPages"]["value"]]


@trace
async def download_pdf(session, url):
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            file_name = os.path.basename(urlparse(url).path)
            temp_dir = tempfile.gettempdir()
            file_path = os.path.join(temp_dir, file_name)
            with open(file_path, "wb") as f:
                f.write(await response.read())
            logging.info(f"Downloaded: {file_path}")
            return file_path
    except Exception as e:
        logging.error(f"Error downloading {url}: {e}")
        return None


async def get_or_create_assistant(
    client: AzureOpenAI,
    name: str,
    description: str,
    instructions: str,
    model: str,
    tools: list[dict],
):
    # List existing assistants
    existing_assistants = client.beta.assistants.list()

    # Check if an assistant with the given name already exists
    for assistant in existing_assistants:
        if assistant.name == name:
            logging.info(
                f"Assistant with name '{name}' already exists. Returning the existing assistant. NOTE: We are not updating the assistant. If you see any issues, please delete the assistant and run the flow again."
            )
            return assistant
    # TODO: If the assistant already exists, we can update the instructions and tools
    # Create a new assistant if it does not exist
    new_assistant = client.beta.assistants.create(
        name=name,
        description=description,
        instructions=instructions,
        model=model,
        tools=tools,
    )
    logging.info(f"Created new assistant with name '{name}'.")
    return new_assistant


@trace
async def process_file_with_assistant(
    client: AzureOpenAI,
    file_path: str,
    vector_store_id: str,
    aoaiConnection: AzureOpenAIConnection,
    mesg_queue: asyncio.Queue,
):
    # This call is required to send the assistant response to the user via the message queue
    class EventHandler(AssistantEventHandler):
        @override
        def on_text_created(self, text) -> None:
            # mesg_queue.put_nowait(
            #     Message(status=StatusEnum.success, message=text.value).model_dump_json()
            # ) # This is not needed as the final message is already being sent in the on_message_done method, but we can still log the assistant response
            logging.info(f"Assistant Response: {text.value}")

        def on_tool_call_created(self, tool_call):
            mesg_queue.put_nowait(
                Message(
                    status=StatusEnum.success,
                    message=f"\nassistant > {tool_call.type}\n",
                ).model_dump_json()
            )
            logging.info(f"\nassistant > {tool_call.type}\n")

        @override
        def on_message_done(self, message) -> None:
            logging.info(f"Message done: {message.content}")
            mesg_queue.put_nowait(
                Message(
                    status=StatusEnum.success, message=message.content[0].text.value
                ).model_dump_json()
            )

    try:
        assistant = await get_or_create_assistant(
            client=client,
            name="Web_Research_Assistant",
            description=f"Assistant that answers questions based on the files in the vector store",
            instructions="You are helpful AI assistant that can help summarize the files in less than 100 words. You have access to the file search tool.",
            model="gpt-4o",
            tools=[{"type": "file_search"}],
            # tool_resources={"file_search": {"vector_store_ids": [vector_store_id]}}, # This is not needed as we are passing the vector store id in the thread creation, but we need to still pass the tool in the assistant creation
        )

        thread = client.beta.threads.create(
            messages=[
                {
                    "role": "user",
                    "content": f"summarise each file one by one in less than 100 words. Please include the file name at the beginning in each file summary in markdown format.",
                }
            ],
            tool_resources={"file_search": {"vector_store_ids": [vector_store_id]}},
        )

        with client.beta.threads.runs.stream(
            thread_id=thread.id,
            assistant_id=assistant.id,
            instructions=f"summarise each file one by one in less than 100 words. Please include the file name at the beginning in each file summary in markdown format.",
            event_handler=EventHandler(),
        ) as stream:
            # We have event handlers to process the messages from the assistant
            stream.until_done()

        # TODO: Test with create_and_run_thread_stream method
        # with client.beta.threads.create_and_run_stream(
        #     thread_id=thread.id,
        #     assistant_id=assistant.id,
        #     instructions=f"summarise each file one by one in less than 100 words. Please include the file name at the beginning in each file summary in markdown format.",
        #     event_handler=EventHandler(),
        # ) as stream:
        #     stream.until_done()

        mesg_queue.put_nowait(
            Message(
                status=StatusEnum.success,
                message=f"### Finished processing {os.path.basename(file_path)}\n",
            ).model_dump_json()
        )

    except Exception as e:
        logging.error(f"Error processing file {file_path}: {e}")
        mesg_queue.put_nowait(
            Message(
                status=StatusEnum.error,
                message=f"Error processing {os.path.basename(file_path)}",
                details={"error": str(e)},
            ).model_dump_json()
        )

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
        client.beta.threads.delete(
            thread.id
        )  # Clean up: Delete the thread after processing


@trace
async def add_to_oai_assistant(
    client: AzureOpenAI,
    files: list,
    aoaiConnection: AzureOpenAIConnection,
    mesg_queue: asyncio.Queue,
):

    try:
        # Create a vector store
        vector_store = client.beta.vector_stores.create(name=f"data-{uuid.uuid4()}")
        file_streams = [open(path, "rb") for path in files]

        # Upload the files to the vector store
        file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
            vector_store_id=vector_store.id, files=file_streams
        )
        logging.info(f"File Batch Upload Status: {file_batch.status}")

        # Parallel processing of files with the assistant
        process_tasks = [
            process_file_with_assistant(
                client, file, vector_store.id, aoaiConnection, mesg_queue
            )
            for file in files
        ]
        await asyncio.gather(*process_tasks)

    except Exception as e:
        logging.error(f"Error processing files: {e}")
        await mesg_queue.put(
            Message(
                status=StatusEnum.error,
                message="Error during processing.",
                details={"error": str(e)},
            ).model_dump_json()
        )

    finally:
        # Ensure all file streams are closed
        for stream in file_streams:
            stream.close()
        # Clean up: Delete the entire vector store after processing
        client.beta.vector_stores.delete(vector_store_id=vector_store.id)
        # TODO: Delete the assistant as well?


@tool
async def my_python_tool(
    question: str,
    realtime_api_search: CustomConnection,
    aoaiConnection: AzureOpenAIConnection,
    test: bool,
    timeout: int = 60,
    filetype: str = "pdf",
):
    if test:
        question = f"site:example.com filetype:{filetype} {question}"
        yield Message(
            status=StatusEnum.success,
            message=f"### Test mode enabled. Using query: {question}\n",
        ).model_dump_json()
        return
    client = AzureOpenAI(
        api_key=aoaiConnection.secrets["api_key"],
        api_version="2024-05-01-preview",
        azure_endpoint=aoaiConnection.configs["api_base"],
    )
    mesg_queue = asyncio.Queue()
    await mesg_queue.put(
        Message(
            status=StatusEnum.in_progress, message="### Searching for PDFs\n"
        ).model_dump_json()
    )

    search_params = {"q": question, "count": 5}

    async with aiohttp.ClientSession() as session:
        pdf_urls = await search_bing_return_pdf_links(
            session, search_params, realtime_api_search, filetype
        )

        download_tasks = [download_pdf(session, url) for url in pdf_urls]
        downloaded_files = await asyncio.gather(*download_tasks)
        downloaded_files = [
            file for file in downloaded_files if file and file.endswith(".pdf")
        ]  # Filter out non-pdf files
        downloaded_files_list = "\n".join([f"- {file}" for file in downloaded_files])

        await mesg_queue.put(
            Message(
                status=StatusEnum.success,
                message=f"### Downloaded files:\n{downloaded_files_list}\n",
            ).model_dump_json()
        )

    process_task = asyncio.create_task(
        add_to_oai_assistant(client, downloaded_files, aoaiConnection, mesg_queue)
    )

    while True:
        try:
            message = await asyncio.wait_for(mesg_queue.get(), timeout=timeout)
            yield message
        except asyncio.TimeoutError:
            break
        await asyncio.sleep(0.1)

    await process_task
    yield Message(
        status=StatusEnum.success, message="### Finished processing the files.\n"
    ).model_dump_json()
