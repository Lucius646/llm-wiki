import os
import re
from pathlib import Path
from datetime import datetime
from slugify import slugify
from typing import List, Dict, Any
from llmwiki.config import settings

def init_wiki_structure(force: bool = False) -> None:
    """Initialize the standard LLM Wiki directory structure"""
    # Create raw directories
    raw_dirs = [
        "assets",
        "articles",
        "papers",
        "notes",
        "books"
    ]

    for dir_name in raw_dirs:
        dir_path = settings.raw_dir / dir_name
        dir_path.mkdir(parents=True, exist_ok=force)
        # Create .gitkeep if directory is empty
        if not any(dir_path.iterdir()):
            (dir_path / ".gitkeep").touch()

    # Create wiki directories
    wiki_dirs = [
        "concepts",
        "entities",
        "sources",
        "synthesis"
    ]

    for dir_name in wiki_dirs:
        dir_path = settings.wiki_dir / dir_name
        dir_path.mkdir(parents=True, exist_ok=force)
        # Create .gitkeep if directory is empty
        if not any(dir_path.iterdir()):
            (dir_path / ".gitkeep").touch()

    # Create index.md if it doesn't exist
    if not settings.index_path.exists() or force:
        index_content = """# Wiki Index

## Concepts
暂无概念页面

## Entities
暂无实体页面

## Sources
暂无资料摘要页面

## Synthesis
暂无综合分析页面
"""
        settings.index_path.write_text(index_content, encoding="utf-8")

    # Create log.md if it doesn't exist
    if not settings.log_path.exists() or force:
        log_content = f"""# Operation Log

## [{datetime.now().strftime('%Y-%m-%d')}] system | LLM Wiki initialized
- Created directory structure
- Initialized index.md and log.md
"""
        settings.log_path.write_text(log_content, encoding="utf-8")

    # Create .env if it doesn't exist
    env_path = settings.wiki_root / ".env"
    if not env_path.exists() or force:
        env_example = settings.wiki_root / ".env.example"
        if env_example.exists():
            env_content = env_example.read_text(encoding="utf-8")
            env_path.write_text(env_content, encoding="utf-8")

def get_wiki_status() -> Dict[str, Any]:
    """Get current wiki status information"""
    def count_files(dir_path: Path) -> int:
        """Count markdown files in directory"""
        if not dir_path.exists():
            return 0
        return len([f for f in dir_path.iterdir() if f.is_file() and f.suffix == ".md" and not f.name.startswith(".")])

    concept_count = count_files(settings.wiki_dir / "concepts")
    entity_count = count_files(settings.wiki_dir / "entities")
    source_count = count_files(settings.wiki_dir / "sources")
    synthesis_count = count_files(settings.wiki_dir / "synthesis")

    total_pages = concept_count + entity_count + source_count + synthesis_count

    # Find last updated file
    last_updated = datetime.fromtimestamp(0)
    for root, _, files in os.walk(settings.wiki_dir):
        for file in files:
            if file.endswith(".md") and not file.startswith("."):
                file_path = Path(root) / file
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if mtime > last_updated:
                    last_updated = mtime

    return {
        "total_pages": total_pages,
        "concept_count": concept_count,
        "entity_count": entity_count,
        "source_count": source_count,
        "synthesis_count": synthesis_count,
        "last_updated": last_updated
    }

def get_operation_log(limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent operation logs from log.md"""
    if not settings.log_path.exists():
        return []

    content = settings.log_path.read_text(encoding="utf-8")
    log_pattern = r'## \[(.*?)\] (\w+) \| (.*?)\n((?:- .*?\n)*'

    matches = re.findall(log_pattern, content, re.DOTALL)
    logs = []

    for match in matches:
        timestamp_str, op_type, description, details_str = match
        try:
            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            try:
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d')
            except ValueError:
                timestamp = datetime.min

        details = []
        if details_str.strip():
            details = [d.strip("- ").strip() for d in details_str.strip().split("\n")]

        logs.append({
            "timestamp": timestamp,
            "type": op_type,
            "description": description,
            "details": details
        })

    # Sort by timestamp descending
    logs.sort(key=lambda x: x["timestamp"], reverse=True)
    return logs[:limit]

def generate_slug(title: str, max_length: int = 60) -> str:
    """Generate a URL-friendly slug from a title"""
    import re
    # 保留中文、英文、数字、空格，其他特殊字符删除
    slug = re.sub(r'[^\w\u4e00-\u9fff\s]', '', title.lower())
    # 空格替换为-
    slug = re.sub(r'\s+', '-', slug)
    # 合并多个连续的-
    slug = re.sub(r'-+', '-', slug).strip('-')
    # 截断到最大长度
    return slug[:max_length]

def get_date_prefix() -> str:
    """Get current date as prefix for filenames"""
    return datetime.now().strftime('%Y-%m-%d')

def extract_frontmatter(content: str) -> Dict[str, Any]:
    """Extract YAML frontmatter from markdown content"""
    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    frontmatter_str = parts[1].strip()
    body = parts[2].strip()

    # Parse simple YAML frontmatter (basic implementation, no external dependency)
    frontmatter = {}
    for line in frontmatter_str.split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            # Handle lists
            if value.startswith("[") and value.endswith("]"):
                value = [v.strip().strip('"').strip("'") for v in value[1:-1].split(",") if v.strip()]
            # Handle booleans
            elif value.lower() == "true":
                value = True
            elif value.lower() == "false":
                value = False
            # Handle numbers
            elif value.isdigit():
                value = int(value)
            elif value.replace(".", "", 1).isdigit():
                value = float(value)
            # Remove quotes from strings
            elif (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            frontmatter[key] = value

    return frontmatter, body

def build_frontmatter(frontmatter: Dict[str, Any]) -> str:
    """Build YAML frontmatter string from dictionary"""
    lines = ["---"]
    for key, value in frontmatter.items():
        if isinstance(value, list):
            value_str = "[" + ", ".join(f'"{v}"' for v in value) + "]"
        elif isinstance(value, bool):
            value_str = str(value).lower()
        else:
            value_str = str(value)
        lines.append(f"{key}: {value_str}")
    lines.append("---\n")
    return "\n".join(lines)

def update_index(page_path: Path, title: str, page_type: str) -> None:
    """Update index.md directory with new/updated page"""
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
    new_entry = f"- [{title}]({relative_path})"

    # 找到对应分类，插入新条目
    if section_title in content:
        parts = content.split(section_title, 1)
        before = parts[0]
        rest = parts[1]

        # 找下一个二级标题的位置
        next_section_pos = rest.find("\n## ")
        if next_section_pos == -1:
            # 分类在最后，直接追加
            if new_entry not in rest:
                new_content = before + section_title + "\n" + new_entry + rest
            else:
                new_content = content
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

def add_log_entry(op_type: str, description: str, details: List[str] = None) -> None:
    """Add operation record to log.md"""
    log_path = settings.log_path
    content = log_path.read_text(encoding="utf-8")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"\n## [{timestamp}] {op_type} | {description}\n"
    if details:
        for detail in details:
            log_entry += f"- {detail}\n"

    # 插入到开头，在log.md的标题之后
    content = content.replace("# Operation Log\n", "# Operation Log\n" + log_entry)
    log_path.write_text(content, encoding="utf-8")
