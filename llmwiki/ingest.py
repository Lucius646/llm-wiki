from pathlib import Path
from typing import Dict, Any, Optional, List
from llmwiki.parsers import parse_markdown, parse_pdf, parse_docx, parse_web, parse_audio
from llmwiki.llm_client import get_llm_client
from llmwiki.git_utils import commit_changes
from llmwiki.utils import generate_slug, get_date_prefix, build_frontmatter, extract_frontmatter, update_index, add_log_entry
from llmwiki.config import settings
import json

def _analyze_content_with_llm(content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """调用LLM分析内容，提取元数据、分类、标签、相关知识点"""
    client = get_llm_client()
    prompt = f"""
    你是LLM Wiki的智能内容分析师，请分析以下内容，返回JSON格式的分析结果：

    内容标题：{metadata.get('title', '无标题')}
    内容来源：{metadata.get('source', '未知来源')}
    内容正文（前8000字）：
    {content[:8000]}

    请严格按照以下JSON结构返回，不要额外解释：
    {{
        "topic": "内容所属的分类，比如：人工智能、编程、历史、管理，如果是技术文档尽量细分，不要用uncategorized",
        "type": "内容类型，只能是这三个值：source（原始资料）、concept（概念/知识点）、entity（实体/人物/产品）",
        "title": "适合作为Wiki页面的标题，简洁准确",
        "summary": "200字以内的内容摘要，提炼核心观点",
        "key_points": ["核心要点1", "核心要点2", "核心要点3"... 最多10条],
        "tags": ["标签1", "标签2", "标签3"... 最多8个，全小写，空格换成短横线],
        "related_concepts": ["内容提到的相关概念、术语，适合单独建页面的"],
        "related_entities": ["内容提到的相关实体、人物、产品、组织，适合单独建页面的"],
        "conflict_notes": "如果内容有和普遍认知冲突的观点，说明冲突点，没有就返回空字符串"
    }}
    """

    messages = [
        {"role": "system", "content": "你是专业的知识库内容分析师，只返回JSON，不返回其他任何内容"},
        {"role": "user", "content": prompt}
    ]

    response = client.chat_completion(messages, temperature=0.1)
    # 清理可能的markdown标记
    response = response.strip().strip("```json").strip("```").strip()
    return json.loads(response)

def _generate_page_content(analysis: Dict[str, Any], raw_path: Path, content: str) -> str:
    """生成符合规范的Wiki页面内容"""
    frontmatter = {
        "title": analysis["title"],
        "type": analysis["type"],
        "tags": analysis["tags"],
        "created_at": get_date_prefix(),
        "updated_at": get_date_prefix(),
        "source_count": 1
    }

    content_parts = [
        build_frontmatter(frontmatter),
        f"# {analysis['title']}\n",
        "## 摘要\n",
        analysis["summary"] + "\n",
        "## 核心要点\n"
    ]
    for point in analysis["key_points"]:
        content_parts.append(f"- {point}\n")

    content_parts.append("\n## 详细内容\n")
    # 截取详细内容，避免过长
    if len(content) > 5000:
        content_parts.append(content[:5000] + "\n\n... 内容过长已截断，查看原始资料获取完整内容\n")
    else:
        content_parts.append(content + "\n")

    # 相关链接部分
    content_parts.append("\n## 相关链接\n")
    # TODO: 后续自动添加已有相关页面的链接

    # 引用来源部分
    relative_raw_path = raw_path.relative_to(settings.wiki_root)
    content_parts.append("\n## 引用来源\n")
    content_parts.append(f"- [{analysis['title']}](/{relative_raw_path})\n")

    if analysis["conflict_notes"]:
        content_parts.append(f"\n> ⚠️ 冲突提示：{analysis['conflict_notes']}\n")

    return "".join(content_parts)

def _update_index(page_path: Path, title: str, page_type: str) -> None:
    """更新index.md目录"""
    index_path = settings.index_path
    content = index_path.read_text(encoding="utf-8")

    # 确定分类标题
    type_mapping = {
        "concept": "## Concepts",
        "entity": "## Entities",
        "source": "## Sources",
        "synthesis": "## Synthesis"
    }
    section_title = type_mapping.get(page_type, "## Concepts")

    # 相对路径
    relative_path = page_path.relative_to(settings.wiki_dir)
    new_entry = f"- [{title}]({relative_path})\n"

    # 找到对应分类，插入新条目
    if section_title in content:
        parts = content.split(section_title, 1)
        before = parts[0]
        rest = parts[1]

        # 找下一个二级标题的位置
        next_section_pos = rest.find("\n## ")
        if next_section_pos == -1:
            new_content = before + section_title + "\n" + new_entry + rest
        else:
            section_content = rest[:next_section_pos]
            after = rest[next_section_pos:]
            # 去重，如果条目已经存在就不重复加
            if new_entry.strip() not in section_content:
                section_content = section_content.rstrip() + "\n" + new_entry
            new_content = before + section_title + section_content + after

        index_path.write_text(new_content, encoding="utf-8")
    else:
        # 如果分类不存在，添加到末尾
        content += f"\n{section_title}\n{new_entry}"
        index_path.write_text(content, encoding="utf-8")

def _add_log_entry(op_type: str, description: str, details: List[str] = None) -> None:
    """添加操作记录到log.md"""
    log_path = settings.log_path
    content = log_path.read_text(encoding="utf-8")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"\n## [{timestamp}] {op_type} | {description}\n"
    if details:
        for detail in details:
            log_entry += f"- {detail}\n"

    # 插入到开头
    content = content.replace("# Operation Log\n", "# Operation Log\n" + log_entry)
    log_path.write_text(content, encoding="utf-8")

def ingest_source(path: str, topic: Optional[str] = None, auto_approve: bool = False) -> Dict[str, Any]:
    """
    Ingest a source file or URL into the wiki

    Args:
        path: Local file path or URL
        topic: Topic category for the source (auto-detected if not provided)
        auto_approve: Auto-approve changes without confirmation

    Returns:
        Ingestion result with changed pages information
    """
    changed_pages = []
    new_pages = []
    updated_pages = []

    # Step1: 识别来源类型并解析内容
    if path.startswith(("http://", "https://")):
        content, metadata = parse_web(path)
    else:
        file_path = Path(path)
        if not file_path.exists():
            raise ValueError(f"File not found: {path}")

        suffix = file_path.suffix.lower()
        if suffix in [".md", ".txt"]:
            content, metadata = parse_markdown(file_path)
        elif suffix == ".pdf":
            content, metadata = parse_pdf(file_path)
        elif suffix in [".docx", ".doc"]:
            content, metadata = parse_docx(file_path)
        elif suffix in [".mp3", ".wav", ".m4a", ".flac"]:
            content, metadata = parse_audio(file_path)
        else:
            raise ValueError(f"Unsupported file type: {suffix}")

    # Step2: 调用LLM分析内容
    analysis = _analyze_content_with_llm(content, metadata)
    final_topic = topic or analysis["topic"]

    # Step3: 保存原始资料到raw目录
    slug = generate_slug(analysis["title"])
    date_prefix = get_date_prefix()
    raw_file_name = f"{date_prefix}-{slug}.md"
    raw_topic_dir = settings.get_raw_topic_dir(final_topic)
    raw_topic_dir.mkdir(exist_ok=True, parents=True)
    raw_file_path = raw_topic_dir / raw_file_name

    raw_content = build_frontmatter({
        "title": analysis["title"],
        "source": path,
        "author": metadata.get("author", "Unknown"),
        "published_date": metadata.get("published_date", "Unknown"),
        "ingested_date": get_date_prefix(),
        "topic": final_topic
    }) + "\n" + content

    raw_file_path.write_text(raw_content, encoding="utf-8")
    changed_pages.append(str(raw_file_path.relative_to(settings.wiki_root)))
    new_pages.append(str(raw_file_path.relative_to(settings.wiki_root)))

    # Step4: 生成对应的Wiki页面
    page_content = _generate_page_content(analysis, raw_file_path, content)
    page_slug = generate_slug(analysis["title"])

    # 确定页面保存目录
    type_dir_mapping = {
        "concept": "concepts",
        "entity": "entities",
        "source": "sources",
        "synthesis": "synthesis"
    }
    page_dir = settings.wiki_dir / type_dir_mapping[analysis["type"]] / final_topic.lower().replace(" ", "-")
    page_dir.mkdir(exist_ok=True, parents=True)
    page_path = page_dir / f"{page_slug}.md"

    # 检查页面是否已存在
    if page_path.exists():
        # 已存在的页面，更新内容
        existing_content = page_path.read_text(encoding="utf-8")
        existing_frontmatter, existing_body = extract_frontmatter(existing_content)
        # 更新frontmatter的更新时间和来源计数
        existing_frontmatter["updated_at"] = get_date_prefix()
        existing_frontmatter["source_count"] = existing_frontmatter.get("source_count", 1) + 1
        # 合并内容，保留现有内容，追加新内容
        merged_content = build_frontmatter(existing_frontmatter) + "\n" + existing_body + "\n\n---\n\n### 新增内容（来自" + path + "）\n" + content
        page_path.write_text(merged_content, encoding="utf-8")
        updated_pages.append(str(page_path.relative_to(settings.wiki_root)))
    else:
        # 新建页面
        page_path.write_text(page_content, encoding="utf-8")
        new_pages.append(str(page_path.relative_to(settings.wiki_root)))
    changed_pages.append(str(page_path.relative_to(settings.wiki_root)))

    # Step5: 更新index.md目录
    _update_index(page_path, analysis["title"], analysis["type"])
    changed_pages.append("wiki/index.md")

    # Step6: 更新log.md
    log_details = [
        f"原始资料：{raw_file_path.relative_to(settings.wiki_root)}",
        f"生成页面：{page_path.relative_to(settings.wiki_root)}"
    ]
    _add_log_entry("ingest", f"新增资料：{analysis['title']}", log_details)
    changed_pages.append("wiki/log.md")

    # Step7: 自动Git提交
    if settings.git_auto_commit:
        commit_msg = f"[ingest] 新增资料：{analysis['title']} | 变更{len(changed_pages)}个页面"
        commit_changes(commit_msg, changed_pages)

    return {
        "changed_pages": len(changed_pages),
        "new_pages": new_pages,
        "updated_pages": updated_pages,
        "changed_files": changed_pages
    }
