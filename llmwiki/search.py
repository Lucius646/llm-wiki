from typing import List, Dict, Any
from pathlib import Path
from llmwiki.config import settings

def search_wiki(keyword: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search wiki content for keywords

    Args:
        keyword: Search keyword
        limit: Maximum number of results

    Returns:
        List of search results with title, path, score, preview
    """
    # TODO: Implement full search functionality using Whoosh
    print(f"DEBUG: Searching for '{keyword}', limit: {limit}")

    # Simple placeholder implementation
    results = []
    for root, _, files in os.walk(settings.wiki_dir):
        for file in files:
            if file.endswith(".md") and not file.startswith(".") and file not in ["index.md", "log.md"]:
                file_path = Path(root) / file
                content = file_path.read_text(encoding="utf-8")
                if keyword.lower() in content.lower():
                    # Extract preview
                    pos = content.lower().find(keyword.lower())
                    preview_start = max(0, pos - 50)
                    preview_end = min(len(content), pos + len(keyword) + 50)
                    preview = "..." + content[preview_start:preview_end].replace("\n", " ") + "..."

                    # Extract title
                    frontmatter, body = extract_frontmatter(content)
                    title = frontmatter.get("title", file_path.stem)

                    results.append({
                        "title": title,
                        "path": str(file_path.relative_to(settings.wiki_root)),
                        "score": 1.0,
                        "preview": preview
                    })
                    if len(results) >= limit:
                        break
        if len(results) >= limit:
            break

    return results

def search_relevant_pages(question: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Search for pages relevant to a question (used by query function)

    Args:
        question: User's question
        limit: Maximum number of relevant pages to return

    Returns:
        List of relevant pages with content
    """
    # TODO: Implement semantic search
    print(f"DEBUG: Finding relevant pages for: {question}")

    # Simple placeholder implementation - search for keywords in question
    keywords = question.split()
    relevant_pages = []

    for keyword in keywords:
        results = search_wiki(keyword, limit=limit)
        relevant_pages.extend(results)

    # Deduplicate
    seen_paths = set()
    unique_pages = []
    for page in relevant_pages:
        if page['path'] not in seen_paths:
            seen_paths.add(page['path'])
            # Read full content
            file_path = settings.wiki_root / page['path']
            content = file_path.read_text(encoding="utf-8")
            page['content'] = content
            unique_pages.append(page)
            if len(unique_pages) >= limit:
                break

    return unique_pages
