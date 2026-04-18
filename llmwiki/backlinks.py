import os
import re
from typing import List, Dict, Any, Tuple
from pathlib import Path
from llmwiki.config import settings
from llmwiki.utils import extract_frontmatter

def parse_obsidian_links(content: str) -> List[Dict[str, Any]]:
    """
    解析内容中的Obsidian格式双链 [[页面标题]] 或 [[页面标题|显示文本]]

    Args:
        content: 页面内容

    Returns:
        链接列表，每个链接包含text、target、alias字段
    """
    links = []
    # 匹配Obsidian双链格式：[[目标页面|别名]] 或 [[目标页面]]
    link_pattern = re.compile(r'\[\[([^|\]]+)(?:\|([^\]]+))?\]\]')
    matches = link_pattern.finditer(content)

    for match in matches:
        target = match.group(1).strip()
        alias = match.group(2).strip() if match.group(2) else None
        text = alias if alias else target
        # 获取上下文片段
        start = max(0, match.start() - 50)
        end = min(len(content), match.end() + 50)
        snippet = content[start:end].replace("\n", " ").strip()
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."

        links.append({
            "text": text,
            "target": target,
            "alias": alias,
            "snippet": snippet,
            "match": match.group(0)
        })

    return links

def _get_all_page_titles() -> Dict[str, str]:
    """获取所有页面的标题到相对路径的映射"""
    title_map = {}
    for root, _, files in os.walk(settings.wiki_dir):
        for file in files:
            if file.endswith(".md") and not file.startswith(".") and file not in ["index.md", "log.md"]:
                file_path = Path(root) / file
                try:
                    content = file_path.read_text(encoding="utf-8")
                    frontmatter, _ = extract_frontmatter(content)
                    title = frontmatter.get("title", "").strip()
                    if title:
                        rel_path = str(file_path.relative_to(settings.wiki_dir)).replace("\\", "/")
                        title_map[title.lower()] = rel_path
                        # 也支持不带后缀的路径匹配
                        title_map[rel_path.lower().replace(".md", "")] = rel_path
                except Exception as e:
                    print(f"Warning: Failed to read {file_path}: {e}")
    return title_map

def get_backlinks(page_path: str) -> List[Dict[str, Any]]:
    """
    获取指定页面的反向链接列表

    Args:
        page_path: 页面的相对路径，比如"concepts/rag.md"

    Returns:
        反向链接列表，每个链接包含source_page、link_text、snippet字段
    """
    backlinks = []
    page_path_lower = page_path.lower()

    # 获取所有页面标题映射
    title_map = _get_all_page_titles()
    # 反向查找：目标路径 -> 页面标题
    target_titles = []
    for title, path in title_map.items():
        if path.lower() == page_path_lower:
            target_titles.append(title)

    # 遍历所有页面，查找引用了当前页面的链接
    for root, _, files in os.walk(settings.wiki_dir):
        for file in files:
            if file.endswith(".md") and not file.startswith(".") and file not in ["index.md", "log.md"]:
                file_path = Path(root) / file
                rel_path = str(file_path.relative_to(settings.wiki_dir)).replace("\\", "/")
                if rel_path == page_path:
                    continue  # 跳过自身页面

                try:
                    content = file_path.read_text(encoding="utf-8")
                    _, body = extract_frontmatter(content)

                    # 1. 检查普通Markdown链接
                    md_links = re.findall(r'\[([^\]]+)\]\((?!http|https)([^)]+)\)', body)
                    for link_text, link_target in md_links:
                        target_path = link_target.strip()
                        # 转换为相对路径比较
                        abs_target = settings.wiki_dir / target_path
                        if abs_target.exists():
                            target_rel = str(abs_target.relative_to(settings.wiki_dir)).replace("\\", "/")
                            if target_rel.lower() == page_path_lower:
                                # 找到引用，获取上下文片段
                                pos = body.find(f"[{link_text}]({link_target})")
                                start = max(0, pos - 50)
                                end = min(len(body), pos + 50)
                                snippet = body[start:end].replace("\n", " ").strip()
                                if start > 0:
                                    snippet = "..." + snippet
                                if end < len(body):
                                    snippet = snippet + "..."

                                backlinks.append({
                                    "source_page": rel_path,
                                    "link_text": link_text,
                                    "snippet": snippet,
                                    "link_type": "markdown"
                                })

                    # 2. 检查Obsidian双链
                    obsidian_links = parse_obsidian_links(body)
                    for link in obsidian_links:
                        target = link["target"].lower()
                        if target in title_map and title_map[target].lower() == page_path_lower:
                            # 找到双链引用
                            backlinks.append({
                                "source_page": rel_path,
                                "link_text": link["text"],
                                "snippet": link["snippet"],
                                "link_type": "obsidian"
                            })

                except Exception as e:
                    print(f"Warning: Failed to process {file_path}: {e}")

    return backlinks

def render_backlinks_section(backlinks: List[Dict[str, Any]], format: str = "markdown") -> str:
    """
    渲染反向链接部分的内容

    Args:
        backlinks: 反向链接列表
        format: 输出格式，支持markdown或html

    Returns:
        渲染后的反向链接内容
    """
    if not backlinks:
        return ""

    if format == "markdown":
        section = "\n\n---\n\n## 反向链接\n"
        for bl in backlinks:
            page_title = bl["source_page"].split("/")[-1].replace(".md", "").replace("-", " ").title()
            section += f"- [{page_title}]({bl['source_page']}): {bl['snippet']}\n"
        return section
    elif format == "html":
        section = "<hr><div class='backlinks'>"
        section += "<h3>反向链接</h3><ul>"
        for bl in backlinks:
            page_title = bl["source_page"].split("/")[-1].replace(".md", "").replace("-", " ").title()
            section += f"<li><a href='{bl['source_page']}'>{page_title}</a>: {bl['snippet']}</li>"
        section += "</ul></div>"
        return section
    else:
        raise ValueError(f"Unsupported format: {format}")

def inject_backlinks_to_page(page_path: str, content: str) -> str:
    """
    将反向链接注入到页面内容的末尾

    Args:
        page_path: 页面相对路径
        content: 原始页面内容

    Returns:
        注入反向链接后的内容
    """
    backlinks = get_backlinks(page_path)
    if not backlinks:
        return content

    # 移除已经存在的反向链接部分
    content = re.sub(r'\n\n---\n\n## 反向链接\n.*', '', content, flags=re.DOTALL)

    # 添加新的反向链接
    backlinks_section = render_backlinks_section(backlinks)
    return content + backlinks_section
