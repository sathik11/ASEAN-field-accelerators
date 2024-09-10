import aiohttp
import asyncio
import logging
import os
import re
import tempfile
import tldextract
import uuid
from enum import Enum
from openai import AssistantEventHandler, AzureOpenAI
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_random_exponential
from promptflow.connections import CustomConnection
from promptflow.tracing import trace
from typing_extensions import override
from urllib.parse import urlparse


class StatusEnum(str, Enum):
    success = "success"
    error = "error"
    in_progress = "in_progress"


class Message(BaseModel):
    status: StatusEnum
    message: str
    details: dict = Field(default_factory=dict)


class WebResearcher:
    def __init__(self, mesg_queue: asyncio.Queue):
        self.mesg_queue = mesg_queue

    @trace
    async def extract_domain_and_query(self, query: str) -> tuple[str, str]:
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
        self,
        session: aiohttp.ClientSession,
        query_params: dict,
        bingConnection: CustomConnection,
        file_type: str = "pdf",
    ) -> list[str]:
        BING_API_KEY = bingConnection.secrets["key"]
        headers = {"Ocp-Apim-Subscription-Key": BING_API_KEY}
        query = query_params["q"]
        domain, query_text = await self.extract_domain_and_query(query)

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
                await self.mesg_queue.put(
                    Message(
                        status=StatusEnum.success,
                        message=f"Downloading files - {pdf_links}\n",
                    ).model_dump_json()
                )
                return pdf_links
        except aiohttp.ClientError as e:
            logging.error(
                f"Error fetching results from Bing. Query: {query_params}. Error: {e}"
            )
            raise

    async def download_pdf(
        self,
        session: aiohttp.ClientSession,
        url: str,
        semaphore: asyncio.Semaphore,
    ) -> str:
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
                    await self.mesg_queue.put(
                        Message(
                            status=StatusEnum.success,
                            message=f"Downloaded url {url} to tmp location:\n{file_path}\n",
                        ).model_dump_json()
                    )
                    return file_path
            except Exception as e:
                logging.error(f"Error downloading {url}: {e}")
                await self.mesg_queue.put(
                    Message(
                        status=StatusEnum.success,
                        message=f"Error downloading {url}: {e}\n",
                    ).model_dump_json()
                )
                return None

    async def get_or_create_assistant(
        self,
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

    async def process_files_with_assistant(self, client: AzureOpenAI, files: list[str]):
        class EventHandler(AssistantEventHandler):
            def __init__(self, mesg_queue: asyncio.Queue = self.mesg_queue):
                super().__init__()
                self.mesg_queue = mesg_queue

            @override
            def on_message_done(self, message) -> None:
                print(f"Message done: {message.content}")
                self.mesg_queue.put_nowait(
                    Message(
                        status=StatusEnum.success, message=message.content[0].text.value
                    ).model_dump_json()
                )

        try:
            vector_store_name = f"data-{uuid.uuid4()}"
            vector_store = client.beta.vector_stores.create(name=vector_store_name)
            await self.mesg_queue.put(
                Message(
                    status=StatusEnum.success,
                    message=f"Created vector store - {vector_store_name}\n",
                ).model_dump_json()
            )
            file_streams = [open(path, "rb") for path in files]

            file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
                vector_store_id=vector_store.id, files=file_streams
            )
            print(f"File Batch Upload Status: {file_batch.status}")

            await self.mesg_queue.put(
                Message(
                    status=StatusEnum.success,
                    message=f"Files added to Vectore store - Status: {file_batch.status}\n",
                ).model_dump_json()
            )

            assistant = await self.get_or_create_assistant(
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

            await self.mesg_queue.put(
                Message(
                    status=StatusEnum.success,
                    message=f"Creating Asisstance API thread with Vectore store for Summarisation\n",
                ).model_dump_json()
            )

            with client.beta.threads.runs.stream(
                thread_id=thread.id,
                assistant_id=assistant.id,
                instructions="Summarize all the files one by one in less than 100 words. Include the file name in the summary. Output in markdown format only.",
                event_handler=EventHandler(),
            ) as stream:
                stream.until_done()

        except Exception as e:
            logging.error(f"Error processing files: {e}")
            await self.mesg_queue.put(
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
            await self.mesg_queue.put(None)

    async def run(
        self,
        search_params: dict,
        realtime_api_search: CustomConnection,
        filetype: str,
        client: AzureOpenAI,
    ):
        async with aiohttp.ClientSession() as session:
            semaphore = asyncio.Semaphore(5)
            pdf_urls = await self.search_bing_return_pdf_links(
                session, search_params, realtime_api_search, filetype
            )

            download_tasks = [
                self.download_pdf(session, url, semaphore) for url in pdf_urls
            ]
            downloaded_files = await asyncio.gather(*download_tasks)
            downloaded_files = [
                file for file in downloaded_files if file and file.endswith(".pdf")
            ]

            downloaded_files_list = "\n".join(
                [f"- {file}" for file in downloaded_files]
            )
            await self.mesg_queue.put(
                Message(
                    status=StatusEnum.success,
                    message=f"### Downloaded files:\n{downloaded_files_list}\n",
                ).model_dump_json()
            )

        process_task = asyncio.create_task(
            self.process_files_with_assistant(client, downloaded_files)
        )
        return process_task
