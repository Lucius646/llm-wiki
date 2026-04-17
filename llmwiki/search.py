import os
import re
from pathlib import Path
from typing import List, Dict, Any
from llmwiki.config import settings
from llmwiki.utils import extract_frontmatter

def _calculate_relevance_score(content: str, title: str, tags: List[str], keywords: List[str]) -> int:
    """计算页面和搜索关键词的相关性得分"""
    score = 0
    content_lower = content.lower()
    title_lower = title.lower()

    for keyword in keywords:
        kw_lower = keyword.lower()
        # 标题匹配权重最高
        if kw_lower in title_lower:
            score += 20
        # 标签匹配权重次之
        for tag in tags:
            if kw_lower in str(tag).lower():
                score += 10
        # 内容匹配按出现次数加权
        count = content_lower.count(kw_lower)
        score += count * 3
        # 完整短语匹配额外加分
        if kw_lower in content_lower:
            score += 5

    return score

def _extract_preview(content: str, keywords: List[str], length: int = 200) -> str:
    """提取包含关键词的上下文预览"""
    content_lower = content.lower()
    min_pos = len(content)

    # 找到第一个出现的关键词位置
    for kw in keywords:
        pos = content_lower.find(kw.lower())
        if pos != -1 and pos < min_pos:
            min_pos = pos

    if min_pos == len(content):
        # 没有找到关键词，取开头
        preview = content[:length].replace("\n", " ").strip()
    else:
        # 取关键词前后的内容
        start = max(0, min_pos - length//2)
        end = min(len(content), min_pos + length//2)
        preview = content[start:end].replace("\n", " ").strip()

    # 超过长度则截断
    if len(preview) > length:
        preview = preview[:length-3] + "..."

    # 开头不是从完整句子开始的话，加上省略号
    if start > 0:
        preview = "..." + preview

    return preview

def search_wiki(keyword: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search wiki content for keywords
    Args:
        keyword: Search keyword
        limit: Maximum number of results
    Returns:
        List of search results with title, path, score, preview, content
    """
    results = []
    keywords = re.split(r'\s+', keyword.strip())

    for root, _, files in os.walk(settings.wiki_dir):
        for file in files:
            if file.endswith(".md") and not file.startswith(".") and file not in ["index.md", "log.md"]:
                file_path = Path(root) / file
                try:
                    content = file_path.read_text(encoding="utf-8")
                    frontmatter, body = extract_frontmatter(content)
                    title = frontmatter.get("title", file_path.stem)
                    tags = frontmatter.get("tags", [])

                    # 计算相关性得分
                    score = _calculate_relevance_score(body, title, tags, keywords)

                    if score > 0:
                        # 提取预览
                        preview = _extract_preview(body, keywords)

                        results.append({
                            "title": title,
                            "path": str(file_path.relative_to(settings.wiki_dir)),
                            "full_path": str(file_path),
                            "score": score,
                            "preview": preview,
                            "content": content,
                            "frontmatter": frontmatter
                        })
                except Exception as e:
                    print(f"Warning: Failed to read {file_path}: {e}")

    # 按得分从高到低排序
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]

def search_relevant_pages(question: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Search for pages relevant to a question (used by query function)
    Args:
        question: User's question
        limit: Maximum number of relevant pages to return
    Returns:
        List of relevant pages with content
    """
    # 提取问题关键词：去掉停用词，拆分关键词
    stop_words = {"什么", "怎么", "如何", "为什么", "是", "的", "了", "吗", "呢", "啊", "我", "你", "他", "我们", "你们", "他们", "这个", "那个", "哪些", "怎么"}
    keywords = [kw for kw in re.split(r'\s+', question.strip()) if kw and kw not in stop_words and len(kw) > 1]

    # 如果没有有效关键词，返回空
    if not keywords:
        return []

    all_results = []
    seen_paths = set()

    # 用每个关键词搜索，合并结果
    for keyword in keywords:
        results = search_wiki(keyword, limit=limit*2)
        for res in results:
            if res["path"] not in seen_paths:
                seen_paths.add(res["path"])
                all_results.append(res)

    # 按总得分排序
    all_results.sort(key=lambda x: x["score"], reverse=True)

    # 限制返回数量，过滤得分过低的结果
    filtered = [res for res in all_results if res["score"] >= 3][:limit]
    return filtered