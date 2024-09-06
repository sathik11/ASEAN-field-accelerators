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
    session: aiohttp.ClientSession, query_params: dict, bingConnection: CustomConnection
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
            "q": f"site:{domain} filetype:pdf {query_text}",
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


@trace
async def process_file_with_assistant(
    file_path: str,
    vector_store_id: str,
    aoaiConnection: AzureOpenAIConnection,
    mesg_queue: asyncio.Queue,
):
    client = AzureOpenAI(
        api_key=aoaiConnection.secrets["api_key"],
        api_version="2024-05-01-preview",
        azure_endpoint=aoaiConnection.configs["api_base"],
    )

    class EventHandler(AssistantEventHandler):
        @override
        def on_text_created(self, text) -> None:
            mesg_queue.put_nowait(
                Message(status=StatusEnum.success, message=text.value).model_dump_json()
            )
            logging.info(f"Assistant Response: {text.value}")

        # @override
        # def on_text_delta(self, delta, snapshot):
        #     mesg_queue.put_nowait(
        #         Message(
        #             status=StatusEnum.success, message=delta.value
        #         ).model_dump_json()
        #     )
        #     logging.info(f"Assistant Delta: {delta.value}")

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
        assistant = client.beta.assistants.create(
            name="pdf-assistant",
            description=f"Assistant that summarizes the PDF file: {os.path.basename(file_path)}",
            instructions="Summarize the content of the file in the vector store. Do not write code.",
            model="gpt-4o",
            tool_resources={"file_search": {"vector_store_ids": [vector_store_id]}},
        )

        thread = client.beta.threads.create(
            messages=[
                {
                    "role": "user",
                    "content": f"Summarize the file: {os.path.basename(file_path)}",
                }
            ],
            tool_resources={"file_search": {"vector_store_ids": [vector_store_id]}},
        )

        with client.beta.threads.runs.stream(
            thread_id=thread.id,
            assistant_id=assistant.id,
            instructions=f"Summarize the file: {os.path.basename(file_path)}",
            event_handler=EventHandler(),
        ) as stream:
            # We have event handlers to process the messages from the assistant
            stream.until_done()

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


@trace
async def add_to_oai_assistant(
    files: list, aoaiConnection: AzureOpenAIConnection, mesg_queue: asyncio.Queue
):
    client = AzureOpenAI(
        api_key=aoaiConnection.secrets["api_key"],
        api_version="2024-05-01-preview",
        azure_endpoint=aoaiConnection.configs["api_base"],
    )

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
                file, vector_store.id, aoaiConnection, mesg_queue
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
        # client.beta.vector_stores.delete(vector_store_id=vector_store.id)


@tool
async def my_python_tool(
    question: str,
    realtime_api_search: CustomConnection,
    aoaiConnection: AzureOpenAIConnection,
    test: bool,
    timeout: int = 60,
):
    if test:
        question = "site:example.com filetype:pdf " + question
        yield Message(
            status=StatusEnum.success,
            message=f"### Test mode enabled. Using query: {question}\n",
        ).model_dump_json()
        return

    mesg_queue = asyncio.Queue()
    await mesg_queue.put(
        Message(
            status=StatusEnum.in_progress, message="### Searching for PDFs\n"
        ).model_dump_json()
    )

    search_params = {"q": question, "count": 5}

    async with aiohttp.ClientSession() as session:
        pdf_urls = await search_bing_return_pdf_links(
            session, search_params, realtime_api_search
        )

        download_tasks = [download_pdf(session, url) for url in pdf_urls]
        downloaded_files = await asyncio.gather(*download_tasks)
        downloaded_files = [file for file in downloaded_files if file]

        await mesg_queue.put(
            Message(
                status=StatusEnum.success,
                message=f"### Downloaded files: {downloaded_files}\n",
            ).model_dump_json()
        )

    process_task = asyncio.create_task(
        add_to_oai_assistant(downloaded_files, aoaiConnection, mesg_queue)
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
