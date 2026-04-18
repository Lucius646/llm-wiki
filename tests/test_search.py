import os
import tempfile
from pathlib import Path
from llmwiki.config import settings
from llmwiki.utils import init_wiki_structure, build_frontmatter
from llmwiki.search import (
    _calculate_relevance_score,
    _extract_preview,
    search_wiki,
    search_relevant_pages
)

def setup_module(module):
    """Setup test environment before all tests"""
    # Create temporary directory for test wiki
    module.tmp_dir = tempfile.TemporaryDirectory()
    module.original_wiki_root = settings.wiki_root
    # Only set wiki_root, other paths are computed properties
    object.__setattr__(settings, 'wiki_root', Path(module.tmp_dir.name))

    # Initialize wiki structure
    init_wiki_structure(force=True)

    # Create test pages
    test_pages = [
        # Page 1: RAG concept
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
RAG的核心流程包括：文档索引构建、用户问题理解、相关文档检索、检索结果增强、回答生成五个步骤。
常见的RAG优化方向包括：向量检索优化、多轮对话上下文管理、检索结果重排序、混合检索策略等。"""
        },
        # Page 2: OpenAI entity
        {
            "path": settings.wiki_dir / "entities/openai.md",
            "frontmatter": {
                "title": "OpenAI",
                "type": "entity",
                "tags": ["人工智能", "大语言模型", "公司"],
                "created_at": "2024-04-17",
                "updated_at": "2024-04-17",
                "source_count": 2
            },
            "content": """OpenAI是美国的人工智能研究公司，成立于2015年，总部位于旧金山。
公司开发了多个知名的大语言模型，包括GPT-3、GPT-4、GPT-4o等，以及DALL-E图像生成模型。
OpenAI的产品包括ChatGPT聊天机器人、API服务平台等，在全球范围内拥有大量用户。
公司的使命是确保通用人工智能能够造福全人类。"""
        },
        # Page 3: GPT-4 concept
        {
            "path": settings.wiki_dir / "concepts/gpt-4.md",
            "frontmatter": {
                "title": "GPT-4",
                "type": "concept",
                "tags": ["大语言模型", "OpenAI", "GPT"],
                "created_at": "2024-04-17",
                "updated_at": "2024-04-17",
                "source_count": 3
            },
            "content": """GPT-4是OpenAI开发的第四代生成式预训练Transformer大语言模型，于2023年3月发布。
它支持多模态输入（文本和图像），在很多专业和学术基准测试中表现出人类水平的性能。
GPT-4相比前代模型GPT-3.5，在推理能力、知识广度、上下文长度支持等方面都有显著提升。
GPT-4被广泛应用于聊天机器人、内容生成、代码开发、辅助研究等多个场景。"""
        }
    ]

    for page in test_pages:
        page["path"].parent.mkdir(exist_ok=True, parents=True)
        full_content = build_frontmatter(page["frontmatter"]) + "\n" + page["content"]
        page["path"].write_text(full_content, encoding="utf-8")

def teardown_module(module):
    """Cleanup test environment after all tests"""
    module.tmp_dir.cleanup()
    # Restore original wiki_root
    object.__setattr__(settings, 'wiki_root', module.original_wiki_root)

def test_calculate_relevance_score():
    """Test relevance score calculation"""
    # Test title match
    score = _calculate_relevance_score("内容", "RAG是什么", ["rag", "检索"], ["rag"])
    assert score >= 20  # Title match gives 20 points

    # Test tag match
    score = _calculate_relevance_score("内容", "测试标题", ["rag", "检索"], ["rag"])
    assert score >= 10  # Tag match gives 10 points

    # Test content match
    score = _calculate_relevance_score("这里提到了RAG技术", "测试标题", ["其他"], ["rag"])
    assert score >= 8  # Content match: 3 per occurrence + 5 for phrase match

    # Test multiple keywords
    score = _calculate_relevance_score("RAG是检索增强生成技术", "RAG介绍", ["rag", "检索"], ["rag", "检索"])
    assert score > 30  # Multiple keywords should sum scores

def test_extract_preview():
    """Test preview extraction"""
    content = """检索增强生成（Retrieval-Augmented Generation，RAG）是一种结合检索系统和大语言模型的技术框架。
它通过在生成回答前先检索外部知识库中的相关信息，能够显著提升回答的准确性、时效性，减少幻觉问题。
RAG技术在近年来得到了广泛的研究和应用，很多公司和研究机构都在开发相关的产品和解决方案。
常见的RAG优化方向包括向量检索优化、多轮对话上下文管理、检索结果重排序、混合检索策略等。
RAG的核心流程包括：文档索引构建、用户问题理解、相关文档检索、检索结果增强、回答生成五个步骤。"""

    # Test keyword in middle (far enough from start to show ...)
    preview = _extract_preview(content, ["核心流程"])
    assert "核心流程" in preview
    assert preview.startswith("...")

    # Test keyword at start
    preview = _extract_preview(content, ["检索增强生成"])
    assert "检索增强生成" in preview
    assert not preview.startswith("...")

    # Test no keyword
    preview = _extract_preview(content, ["不存在的关键词"])
    assert preview == content[:200].replace("\n", " ").strip()

    # Test long content truncation when keyword is in middle
    long_content = "x" * 300 + "keyword" + "x" * 300
    preview = _extract_preview(long_content, ["keyword"])
    assert len(preview) == 200
    assert preview.endswith("...")
    assert "keyword" in preview

def test_search_wiki():
    """Test wiki search functionality"""
    # Search for "RAG"
    results = search_wiki("RAG")
    assert len(results) >= 1
    assert results[0]["title"] == "检索增强生成(RAG)"
    assert results[0]["score"] > 0
    assert "RAG" in results[0]["preview"]

    # Search for "OpenAI"
    results = search_wiki("OpenAI")
    assert len(results) == 2  # Should match openai entity and gpt-4 page
    assert {res["title"] for res in results} == {"OpenAI", "GPT-4"}

    # Search for non-existent keyword
    results = search_wiki("不存在的关键词")
    assert len(results) == 0

    # Test limit parameter
    results = search_wiki("大语言模型", limit=2)
    assert len(results) == 2

def test_search_relevant_pages():
    """Test relevant pages search for query function"""
    # Question with stop words
    results = search_relevant_pages("什么是RAG技术？")
    assert len(results) >= 1
    assert results[0]["title"] == "检索增强生成(RAG)"

    # Question with multiple relevant concepts
    results = search_relevant_pages("OpenAI开发了哪些大模型？")
    assert len(results) >= 2
    assert {res["title"] for res in results} >= {"OpenAI", "GPT-4"}

    # Question with only stop words
    results = search_relevant_pages("什么怎么如何为什么？")
    assert len(results) == 0

    # Test score filtering
    results = search_relevant_pages("不存在的关键词12345")  # Should have no matches
    assert len(results) == 0
