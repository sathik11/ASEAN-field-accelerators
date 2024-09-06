import aiohttp
import asyncio
from promptflow.core import tool
from promptflow.connections import CustomConnection, AzureOpenAIConnection
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

# Define the status enum for consistent status reporting
class StatusEnum(str, Enum):
    success = "success"
    error = "error"
    in_progress = "in_progress"

# Define the Pydantic model for queue messages
class Message(BaseModel):
    status: StatusEnum
    message: str
    details: dict = Field(default_factory=dict)

async def extract_domain_and_query(query: str):
    """
    Extracts the domain and search query from the input string.
    Supports both URLs with and without protocols.
    """
    # Flexible pattern to capture both full URLs (with http/https) and domains without protocols
    url_pattern = r"(https?://[^\s]+|www\.[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"
    url_match = re.search(url_pattern, query)

    if url_match:
        possible_url = url_match.group(0)  # Extract the domain or URL
        query_text = query.replace(possible_url, "").strip()  # Remove URL or domain from query text

        # Add protocol if missing for parsing purposes
        if not possible_url.startswith("http"):
            possible_url = "http://" + possible_url

        # Extract domain using tldextract
        extracted_domain = tldextract.extract(possible_url)
        domain = f"{extracted_domain.domain}.{extracted_domain.suffix}"

        return domain, query_text
    else:
        return None, query  # Return None if no domain is found

# Retry logic for Bing search with exponential backoff
@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
async def search_bing_return_pdf_links(session: aiohttp.ClientSession, query_params: dict, bingConnection: CustomConnection) -> list[str]:
    """
    Uses Bing Search API to search for PDF links based on the provided query.
    Extracts domain and search query from the input and constructs the search request.
    """
    BING_API_KEY = bingConnection.secrets["key"]
    headers = {"Ocp-Apim-Subscription-Key": BING_API_KEY}
    
    # Extract domain and query text from the provided search query
    query = query_params["q"]
    domain, query_text = await extract_domain_and_query(query)

    if not domain:
        logging.error("No domain found in the query.")
        raise ValueError("No valid domain found in the search query.")

    try:
        # Make the Bing API request using the extracted domain and query text
        async with session.get(
            url="https://api.bing.microsoft.com/v7.0/search",
            params={"q": f"site:{domain} filetype:pdf {query_text}", "count": query_params.get("count", 10)},
            headers=headers,
        ) as response:
            response.raise_for_status()
            search_results = await response.json()

            # Extract and return the URLs of the found PDFs
            return [result["url"] for result in search_results["webPages"]["value"]]
    except Exception as e:
        logging.error(f"Error in Bing search: {e}")
        raise

# Function to download PDF files
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

# Function to handle adding PDF to Azure OpenAI assistant and summarizing
async def add_to_oai_assistant(local_pdf_file_paths, aoaiConnection: AzureOpenAIConnection, mesg_queue: asyncio.Queue):
    client = AzureOpenAI(
        api_key=aoaiConnection.secrets["api_key"],
        api_version="2024-05-01-preview",
        azure_endpoint=aoaiConnection.configs["api_base"],
    )

    class EventHandler(AssistantEventHandler):
        @override
        def on_text_created(self, text) -> None:
            mesg_queue.put_nowait(Message(status=StatusEnum.success, message=text.value).model_dump_json())
            logging.info(f"Assistant Response: {text.value}")

        @override
        def on_message_done(self, message) -> None:
            logging.info(f"Message done: {message.content}")
            mesg_queue.put_nowait(Message(status=StatusEnum.success, message=message.content[0].text.value).model_dump_json())

    try:
        vector_store = client.beta.vector_stores.create(name=f"data-{uuid.uuid4()}")
        file_streams = [open(path, "rb") for path in local_pdf_file_paths if path]

        file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
            vector_store_id=vector_store.id, files=file_streams
        )
        logging.info(f"File Batch Upload Status: {file_batch.status}")

        assistant = client.beta.assistants.update(
            name="pdf-assistant",
            description="Assistant that answers questions based on PDF files",
            instructions="Summarize the PDFs one by one.",
            model="gpt-4o",
            assistant_id="asst_2bgNE8kHGgkfN0lk9HpSiZLT",
            tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
        )

        thread = client.beta.threads.create(
            messages=[{"role": "user", "content": "Summarize all the PDFs one by one"}],
            tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
        )

        with client.beta.threads.runs.stream(
            thread_id=thread.id, assistant_id=assistant.id, instructions="Summarize all PDFs", event_handler=EventHandler()
        ) as stream:
            stream.until_done()

    except Exception as e:
        logging.error(f"Error in assistant creation: {e}")
        mesg_queue.put_nowait(Message(status=StatusEnum.error, message="Error during assistant creation.", details={"error": str(e)}).model_dump_json())
    finally:
        for stream in file_streams:
            stream.close()

@tool
async def my_python_tool(question: str, realtime_api_search: CustomConnection, aoaiConnection: AzureOpenAIConnection, test:bool, timeout: int = 60):
    if test:
        question = "site:example.com filetype:pdf " + question
        yield Message(status=StatusEnum.success, message=f"### Test mode enabled. Using query: {question}\n").model_dump_json()
        return
    
    mesg_queue = asyncio.Queue()
    await mesg_queue.put(Message(status=StatusEnum.in_progress, message="### Searching for PDFs\n").model_dump_json())

    search_params = {"q": question, "count": 5}

    async with aiohttp.ClientSession() as session:
        pdf_urls = await search_bing_return_pdf_links(session, search_params, realtime_api_search)

        download_tasks = [download_pdf(session, url) for url in pdf_urls]
        downloaded_files = await asyncio.gather(*download_tasks)
        downloaded_files = [file for file in downloaded_files if file]  # Filter out None results

        await mesg_queue.put(Message(status=StatusEnum.success, message=f"### Downloaded files: {downloaded_files}\n").model_dump_json())

    # Task to process the files
    process_task = asyncio.create_task(add_to_oai_assistant(downloaded_files, aoaiConnection, mesg_queue))

    while True:
        try:
            message = await asyncio.wait_for(mesg_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            break
        await asyncio.sleep(0.1)
        yield message

    await process_task
    yield Message(status=StatusEnum.success, message="### Finished processing the files.\n").model_dump_json()
