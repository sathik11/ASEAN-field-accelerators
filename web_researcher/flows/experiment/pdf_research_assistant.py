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

# logging.basicConfig(level=print)


class StatusEnum(str, Enum):
    success = "success"
    error = "error"
    in_progress = "in_progress"


class Message(BaseModel):
    status: StatusEnum
    message: str
    details: dict = Field(default_factory=dict)


@trace
async def extract_domain_and_query(query: str) -> tuple[str, str]:
    """
    Extract the domain from a query string containing a URL and return the domain and query text.

    Args:
        query: The search query string.

    Returns:
        Tuple containing the extracted domain and the query text.
    """
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
    file_type: str = "pdf",
) -> list[str]:
    """
    Searches Bing and returns a list of URLs for the requested file type (default is PDF).

    Args:
        session: aiohttp.ClientSession instance.
        query_params: Dictionary containing search query parameters.
        bingConnection: CustomConnection object with Bing API credentials.
        file_type: The type of file to search for (default is 'pdf').

    Returns:
        A list of URLs pointing to the requested file type (e.g., PDF files).
    """
    BING_API_KEY = bingConnection.secrets["key"]
    headers = {"Ocp-Apim-Subscription-Key": BING_API_KEY}
    query = query_params["q"]
    domain, query_text = await extract_domain_and_query(query)

    if not domain:
        logging.error(f"No valid domain found in the query: {query}")
        raise ValueError("No valid domain found in the search query.")

    try:
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
            pdf_links = [
                result["url"] for result in search_results["webPages"]["value"]
            ]
            print(f"Links of PDF files: {pdf_links}")
            return pdf_links
    except aiohttp.ClientError as e:
        logging.error(
            f"Error fetching results from Bing. Query: {query_params}. Error: {e}"
        )
        raise


async def download_pdf(
    session: aiohttp.ClientSession, url: str, semaphore: asyncio.Semaphore
) -> str:
    """
    Downloads a PDF from the given URL and saves it to a temporary directory.

    Args:
        session: The aiohttp session object.
        url: The URL to download the PDF from.
        semaphore: Async semaphore to limit concurrent downloads.

    Returns:
        The file path of the downloaded PDF.
    """
    async with semaphore:
        try:
            async with session.get(url) as response:
                response.raise_for_status()
                file_name = os.path.basename(urlparse(url).path)
                temp_dir = tempfile.gettempdir()
                file_path = os.path.join(temp_dir, file_name)
                with open(file_path, "wb") as f:
                    f.write(await response.read())
                print(f"Downloaded: {file_path}")
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
) -> AzureOpenAI:
    """
    Retrieves or creates an Azure OpenAI assistant with the specified configuration.

    Args:
        client: The AzureOpenAI client object.
        name: The name of the assistant.
        description: The description of the assistant.
        instructions: Instructions for the assistant.
        model: Model used by the assistant (e.g., GPT-4).
        tools: List of tools available for the assistant.

    Returns:
        The created or retrieved assistant object.
    """
    existing_assistants = client.beta.assistants.list()

    for assistant in existing_assistants:
        if assistant.name == name:
            print(f"Assistant '{name}' already exists. Returning the existing one.")
            return assistant

    new_assistant = client.beta.assistants.create(
        name=name,
        description=description,
        instructions=instructions,
        model=model,
        tools=tools,
    )
    print(f"Created new assistant with name '{name}'.")
    return new_assistant


@trace
async def process_files_with_assistant(
    client: AzureOpenAI,
    files: list[str],
    mesg_queue: asyncio.Queue,
):
    """
    Adds files to the Azure OpenAI assistant for processing and vectorization, and processes them with the assistant.

    Args:
        client: The AzureOpenAI client object.
        files: List of file paths.
        mesg_queue: The message queue for inter-task communication.
    """

    class EventHandler(AssistantEventHandler):
        @override
        def on_text_created(self, text) -> None:
            print(f"Assistant Response: {text.value}")

        @override
        def on_message_done(self, message) -> None:
            print(f"Message done: {message.content}")
            mesg_queue.put_nowait(
                Message(
                    status=StatusEnum.success, message=message.content[0].text.value
                ).model_dump_json()
            )

    try:
        vector_store = client.beta.vector_stores.create(name=f"data-{uuid.uuid4()}")
        file_streams = [open(path, "rb") for path in files]

        file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
            vector_store_id=vector_store.id, files=file_streams
        )
        print(f"File Batch Upload Status: {file_batch.status}")

        assistant = await get_or_create_assistant(
            client=client,
            name="Web_Research_Assistant",
            description="Assistant that answers questions based on the files in the vector store",
            instructions="You are a helpful AI assistant that can help summarize the files in less than 100 words.",
            model="gpt-4o",
            tools=[{"type": "file_search"}],
        )

        thread = client.beta.threads.create(
            messages=[
                {
                    "role": "user",
                    "content": "Summarize each file in less than 100 words.",
                }
            ],
            tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
        )

        with client.beta.threads.runs.stream(
            thread_id=thread.id,
            assistant_id=assistant.id,
            instructions="Summarize all the files one by one.",
            event_handler=EventHandler(),
        ) as stream:
            stream.until_done()

    except Exception as e:
        logging.error(f"Error processing files: {e}")
        mesg_queue.put_nowait(
            Message(
                status=StatusEnum.error,
                message="Error during processing.",
                details={"error": str(e)},
            ).model_dump_json()
        )
    finally:
        for stream in file_streams:
            stream.close()
        client.beta.vector_stores.delete(vector_store_id=vector_store.id)
        mesg_queue.put_nowait(None)


@tool
async def my_python_tool(
    question: str,
    realtime_api_search: CustomConnection,
    aoaiConnection: AzureOpenAIConnection,
    test: bool,
    timeout: int = 120,
    filetype: str = "pdf",
):
    """
    The main tool function that performs a search, downloads files, and processes them with Azure OpenAI assistant.

    Args:
        question: The user query.
        realtime_api_search: The CustomConnection for Bing API searche.
        aoaiConnection: The AzureOpenAIConnection object.
        test: If true, runs in test mode.
        timeout: Timeout for waiting on queue messages.
        filetype: The type of files to search for (default is 'pdf').
    """

    # async def process_messages(mesg_queue: asyncio.Queue):
    #     while True:
    #         try:
    #             message = await asyncio.wait_for(mesg_queue.get(), timeout=timeout)
    #             yield message
    #         except asyncio.TimeoutError:
    #             break
    #         await asyncio.sleep(0.1)

    mesg_queue = asyncio.Queue(maxsize=100)
    list_of_messages = []

    if test:
        test_query = f"site:example.com filetype:{filetype} {question}"
        await mesg_queue.put(
            Message(
                status=StatusEnum.success,
                message=f"### Test mode enabled. Using query: {test_query}\n",
            ).model_dump_json()
        )

    client = AzureOpenAI(
        api_key=aoaiConnection.secrets["api_key"],
        api_version="2024-05-01-preview",
        azure_endpoint=aoaiConnection.configs["api_base"],
    )
    mesg_queue.put_nowait(
        Message(
            status=StatusEnum.success, message="### Searching for PDFs\n"
        ).model_dump_json()
    )

    search_params = {"q": question, "count": 5}

    async with aiohttp.ClientSession() as session:
        semaphore = asyncio.Semaphore(5)  # Limit concurrent downloads
        pdf_urls = await search_bing_return_pdf_links(
            session, search_params, realtime_api_search, filetype
        )

        download_tasks = [download_pdf(session, url, semaphore) for url in pdf_urls]
        downloaded_files = await asyncio.gather(*download_tasks)
        downloaded_files = [
            file for file in downloaded_files if file and file.endswith(".pdf")
        ]

        downloaded_files_list = "\n".join([f"- {file}" for file in downloaded_files])
        await mesg_queue.put(
            Message(
                status=StatusEnum.success,
                message=f"### Downloaded files:\n{downloaded_files_list}\n",
            ).model_dump_json()
        )

    # Process the downloaded files with the Azure OpenAI assistant - long running task
    process_task = asyncio.create_task(
        process_files_with_assistant(client, downloaded_files, mesg_queue)
    )

    while True:
        try:
            message = await asyncio.wait_for(mesg_queue.get(), timeout=timeout)
            if message is None:
                break
            list_of_messages.append(message)
            yield message
        except asyncio.TimeoutError:
            break
        await asyncio.sleep(0.1)

    print("Waiting for long processing task to complete.")
    await asyncio.wait_for(process_task, timeout=timeout)

    mesg_queue.put_nowait(
        Message(
            status=StatusEnum.success, message="### Finished processing the files.\n"
        ).model_dump_json()
    )
    yield list_of_messages
