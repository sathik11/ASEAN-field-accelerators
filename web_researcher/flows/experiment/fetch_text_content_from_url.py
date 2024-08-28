import os
import re
import tempfile
import asyncio
import aiohttp

from promptflow.connections import CustomConnection
from promptflow.core import tool
from tenacity import retry, stop_after_attempt, wait_random_exponential
from PyPDF2 import PdfReader, PdfWriter


@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
async def search_and_download_pdfs(
    session, query_params: dict, bingConnection: CustomConnection
) -> list[str]:
    BING_API_KEY = bingConnection.secrets["key"]
    headers = {"Ocp-Apim-Subscription-Key": BING_API_KEY}
    url_pattern = r"(.*?)(https?://(?:www\.)?([^/]+))"
    query = query_params["q"]
    match = re.search(url_pattern, query)
    query_text = match.group(1)
    domain = match.group(3)

    async with session.get(
        url="https://api.bing.microsoft.com/v7.0/search",
        params={
            "q": f"site:{domain} filetype:pdf {query_text}",
            "count": query_params.get("count", 5),
        },
        headers=headers,
    ) as response:
        response.raise_for_status()
        search_results = await response.json()
        remote_pdf_urls = [
            result["url"]
            for result in search_results["webPages"]["value"]
            if result["url"].endswith(".pdf")
        ]
        remote_pdf_urls = list(set(remote_pdf_urls))  # Remove duplicates
        tasks = []
        for url in remote_pdf_urls:
            tasks.append(download_pdf(session, url))
        local_pdf_urls = await asyncio.gather(*tasks)
        return local_pdf_urls, remote_pdf_urls


async def download_pdf(session, url):
    async with session.get(url) as response:
        response.raise_for_status()
        temp_dir = tempfile.gettempdir()
        file_name = os.path.basename(url)
        file_path = os.path.join(temp_dir, file_name)
        with open(file_path, "wb") as f:
            f.write(await response.read())
        print(f"Downloaded {file_path}")
        # Truncate the PDF to the first 10 pages
        truncated_file_path = truncate_pdf(file_path)
        return truncated_file_path


def truncate_pdf(file_path):
    reader = PdfReader(file_path)
    writer = PdfWriter()
    for i in range(min(10, len(reader.pages))):
        writer.add_page(reader.pages[i])
    truncated_file_path = file_path.replace(".pdf", "_truncated.pdf")
    with open(truncated_file_path, "wb") as f:
        writer.write(f)
    print(f"Truncated PDF saved to {truncated_file_path}")
    return truncated_file_path


@tool
async def fetch_pdf_from_query(
    query: str, bingConnection: CustomConnection, count: int = 5
) -> dict:
    search_params = {
        "q": query,
        "count": count,
    }
    async with aiohttp.ClientSession() as session:
        local_pdf_urls, remote_pdf_urls = await search_and_download_pdfs(
            session, search_params, bingConnection
        )
        return {
            "local_pdf_urls": local_pdf_urls,
            "remote_pdf_urls": remote_pdf_urls,
        }
