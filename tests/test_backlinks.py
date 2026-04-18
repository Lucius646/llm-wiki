import os
import tempfile
from pathlib import Path
from llmwiki.config import settings
from llmwiki.utils import init_wiki_structure, build_frontmatter
from llmwiki.backlinks import get_backlinks, render_backlinks_section, parse_obsidian_links
from llmwiki.lint import lint_wiki

def setup_module(module):
    """Setup test environment before all tests"""
    # Create temporary directory for test wiki
    module.tmp_dir = tempfile.TemporaryDirectory()
    module.original_wiki_root = settings.wiki_root
    # Only set wiki_root, other paths are computed properties
    object.__setattr__(settings, 'wiki_root', Path(module.tmp_dir.name))

    # Initialize wiki structure
    init_wiki_structure(force=True)

    # Create test pages with links
    test_pages = [
        # Page 1: RAG概念页，被其他页面引用
        {
            "path": settings.wiki_dir / "concepts/rag.md",
            "frontmatter": {
                "title": "检索增强生成(RAG)",
                "type": "concept",
                "tags": ["大语言模型", "检索", "生成"],
                "created_at": "2024-04-17",
                "updated_at": "2024-04-17",
                "source_count": 1
            },
            "content": """检索增强生成（Retrieval-Augmented Generation，RAG）是一种结合检索系统和大语言模型的技术框架。
它通过在生成回答前先检索外部知识库中的相关信息，能够显著提升回答的准确性、时效性，减少幻觉问题。
相关技术：[[大语言模型]]（Obsidian格式双链）、[[向量数据库]]
"""
        },
        # Page 2: 向量数据库页，引用RAG
        {
            "path": settings.wiki_dir / "concepts/vector-db.md",
            "frontmatter": {
                "title": "向量数据库",
                "type": "concept",
                "tags": ["数据库", "检索", "向量"],
                "created_at": "2024-04-17",
                "updated_at": "2024-04-17",
                "source_count": 1
            },
            "content": """向量数据库是专门用于存储和检索向量嵌入的数据库。
它是[[检索增强生成(RAG)]]系统的核心组件之一，用于存储文档的向量表示，支持相似度检索。
常见的向量数据库包括Pinecone、Chroma、Weaviate、Milvus等。
"""
        },
        # Page 3: LLM页面，被RAG引用
        {
            "path": settings.wiki_dir / "concepts/llm.md",
            "frontmatter": {
                "title": "大语言模型",
                "type": "concept",
                "tags": ["大语言模型", "AI"],
                "created_at": "2024-04-17",
                "updated_at": "2024-04-17",
                "source_count": 1
            },
            "content": """大语言模型是一种能够理解和生成人类语言的人工智能模型。
典型代表包括GPT系列、Claude、Llama等。
RAG技术可以有效提升大语言模型回答的准确性：[检索增强生成](concepts/rag.md)（普通Markdown链接）
"""
        },
        # Page 4: 有死链的页面，引用不存在的页面
        {
            "path": settings.wiki_dir / "concepts/test.md",
            "frontmatter": {
                "title": "测试页面",
                "type": "concept",
                "tags": ["测试"],
                "created_at": "2024-04-17",
                "updated_at": "2024-04-17",
                "source_count": 0
            },
            "content": """这个页面引用了不存在的页面：[[不存在的页面]]、[不存在的链接](concepts/not-exist.md)
"""
        }
    ]

    for page in test_pages:
        page["path"].parent.mkdir(exist_ok=True, parents=True)
        full_content = build_frontmatter(page["frontmatter"]) + "\n" + page["content"]
        page["path"].write_text(full_content, encoding="utf-8")

def teardown_module(module):
    """Cleanup test environment after all tests"""
    try:
        module.tmp_dir.cleanup()
    except:
        pass
    # Restore original wiki_root
    object.__setattr__(settings, 'wiki_root', module.original_wiki_root)

def test_parse_obsidian_links():
    """测试解析Obsidian格式的双链"""
    content = """这是普通文本，[[页面标题1]]是双链，[[页面标题2|显示文本]]是带别名的双链。
还有普通链接：[普通链接文本](path/to/page.md)"""

    links = parse_obsidian_links(content)
    assert len(links) == 2

    # 检查第一个双链
    assert links[0]["text"] == "页面标题1"
    assert links[0]["target"] == "页面标题1"
    assert links[0]["alias"] is None

    # 检查第二个带别名的双链
    assert links[1]["text"] == "显示文本"
    assert links[1]["target"] == "页面标题2"
    assert links[1]["alias"] == "显示文本"

def test_get_backlinks_for_page():
    """测试获取页面的反向链接"""
    # RAG页面应该被vector-db.md和llm.md引用
    rag_backlinks = get_backlinks("concepts/rag.md")
    assert len(rag_backlinks) == 2
    source_pages = {link["source_page"] for link in rag_backlinks}
    assert "concepts/vector-db.md" in source_pages
    assert "concepts/llm.md" in source_pages

    # LLM页面应该被rag.md引用
    llm_backlinks = get_backlinks("concepts/llm.md")
    assert len(llm_backlinks) == 1
    assert llm_backlinks[0]["source_page"] == "concepts/rag.md"
    assert llm_backlinks[0]["link_text"] == "大语言模型"

    # vector-db页面应该被rag.md引用
    vector_db_backlinks = get_backlinks("concepts/vector-db.md")
    assert len(vector_db_backlinks) == 1
    assert vector_db_backlinks[0]["source_page"] == "concepts/rag.md"
    assert vector_db_backlinks[0]["link_text"] == "向量数据库"

def test_render_backlinks_section():
    """测试渲染反向链接部分的HTML/Markdown"""
    backlinks = [
        {
            "source_page": "concepts/vector-db.md",
            "link_text": "检索增强生成(RAG)",
            "snippet": "它是[[检索增强生成(RAG)]]系统的核心组件之一"
        },
        {
            "source_page": "concepts/llm.md",
            "link_text": "检索增强生成",
            "snippet": "RAG技术可以有效提升大语言模型回答的准确性：[检索增强生成](concepts/rag.md)"
        }
    ]

    section = render_backlinks_section(backlinks)
    assert "## 反向链接" in section
    assert "concepts/vector-db.md" in section
    assert "concepts/llm.md" in section
    assert "检索增强生成(RAG)" in section
    assert "检索增强生成" in section

def test_backlinks_in_lint_dead_link_detection():
    """测试Lint的死链检测能识别Obsidian双链格式的死链"""
    report = lint_wiki()
    dead_links = [issue for issue in report["issues"] if issue["type"] == "dead_link"]
    # 应该有两个死链：[[不存在的页面]]和[不存在的链接](concepts/not-exist.md)
    assert len(dead_links) >= 2
    dead_targets = [issue["target"] for issue in dead_links]
    assert "不存在的页面" in dead_targets
    assert "concepts/not-exist.md" in dead_targets

def test_backlinks_include_context_snippet():
    """测试反向链接包含上下文片段"""
    rag_backlinks = get_backlinks("concepts/rag.md")
    for bl in rag_backlinks:
        assert "snippet" in bl
        assert len(bl["snippet"]) > 0
        assert bl["link_text"] in bl["snippet"]
