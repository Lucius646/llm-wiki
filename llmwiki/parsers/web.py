from typing import Tuple, Dict, Any
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

def parse_web(url: str) -> Tuple[str, Dict[str, Any]]:
    """
    Extract text content from a web page

    Args:
        url: URL of the web page

    Returns:
        Tuple of (content, metadata)
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')

    # Remove unwanted elements
    for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
        element.decompose()

    # Extract text
    content = soup.get_text(separator="\n\n")
    # Clean up extra newlines
    lines = [line.strip() for line in content.splitlines()]
    content = "\n\n".join(line for line in lines if line)

    # Extract metadata
    title = soup.title.string.strip() if soup.title else urlparse(url).netloc
    author = ""
    description = ""

    meta_author = soup.find("meta", attrs={"name": "author"})
    if meta_author:
        author = meta_author.get("content", "")

    meta_description = soup.find("meta", attrs={"name": "description"})
    if meta_description:
        description = meta_description.get("content", "")

    metadata = {
        "title": title,
        "author": author or "Unknown",
        "description": description,
        "source": url,
        "file_type": "web",
        "domain": urlparse(url).netloc
    }

    return content, metadata
