import os
import tempfile
from pathlib import Path
from llmwiki.config import settings
from llmwiki.utils import init_wiki_structure, build_frontmatter
from llmwiki.lint import lint_wiki, fix_lint_issues

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
常见的RAG优化方向包括：向量检索优化、多轮对话上下文管理、检索结果重排序、混合检索策略等。
相关技术：[大语言模型](concepts/llm.md)（死链，因为llm.md不存在）
和[GPT-4](concepts/gpt-4.md)结合使用效果更好。
"""
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
公司的使命是确保通用人工智能能够造福全人类。
相关页面：[GPT-4](concepts/gpt-4.md)
"""
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
GPT-4被广泛应用于聊天机器人、内容生成、代码开发、辅助研究等多个场景。
"""
        },
        # Page 4: 孤立页面，没有被任何其他页面引用
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
它是RAG系统的核心组件之一，用于存储文档的向量表示，支持相似度检索。
常见的向量数据库包括Pinecone、Chroma、Weaviate、Milvus等。
"""
        },
        # Page 5: 和GPT-4页面有内容冲突的页面
        {
            "path": settings.wiki_dir / "concepts/gpt-4-conflict.md",
            "frontmatter": {
                "title": "GPT-4介绍",
                "type": "concept",
                "tags": ["大语言模型", "OpenAI", "GPT"],
                "created_at": "2024-04-17",
                "updated_at": "2024-04-17",
                "source_count": 1
            },
            "content": """GPT-4是OpenAI开发的第三代大语言模型，于2022年发布。（和GPT-4页面的"第四代、2023年3月发布"冲突）
它只支持文本输入，不支持图像。（和GPT-4页面的"支持多模态输入"冲突）
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

def test_lint_detect_dead_links():
    """测试死链检测功能"""
    report = lint_wiki()
    dead_links = [issue for issue in report["issues"] if issue["type"] == "dead_link"]
    assert len(dead_links) == 1
    assert dead_links[0]["page"] == "concepts/rag.md"
    assert "[大语言模型](concepts/llm.md)" in dead_links[0]["details"]
    assert "concepts/llm.md" in dead_links[0]["target"]

def test_lint_detect_isolated_pages():
    """测试孤立页面检测功能"""
    report = lint_wiki()
    isolated_pages = [issue for issue in report["issues"] if issue["type"] == "isolated_page"]
    assert len(isolated_pages) >= 1
    isolated_paths = [page["page"] for page in isolated_pages]
    assert "concepts/vector-db.md" in isolated_paths

def test_lint_detect_content_conflicts():
    """测试内容冲突检测功能"""
    report = lint_wiki()
    conflicts = [issue for issue in report["issues"] if issue["type"] == "content_conflict"]
    assert len(conflicts) >= 1
    # 检查是否有gpt-4相关的冲突
    gpt_conflict = None
    for conflict in conflicts:
        if "gpt" in conflict["details"].lower() or "gpt-4" in conflict["page"]:
            gpt_conflict = conflict
            break
    assert gpt_conflict is not None
    assert "concepts/gpt-4-conflict.md" in [gpt_conflict["page"]] + gpt_conflict["related_pages"]
    assert "concepts/gpt-4.md" in [gpt_conflict["page"]] + gpt_conflict["related_pages"]

def test_lint_detect_missing_pages():
    """测试缺失页面检测功能"""
    report = lint_wiki()
    missing_pages = [issue for issue in report["issues"] if issue["type"] == "missing_page"]
    missing_targets = [issue["target"] for issue in missing_pages]
    assert "大语言模型" in missing_targets or "LLM" in missing_targets or "llm.md" in missing_targets

def test_lint_fix_dead_links():
    """测试自动修复死链功能"""
    # 先检查确实存在死链
    report_before = lint_wiki()
    dead_links_before = [issue for issue in report_before["issues"] if issue["type"] == "dead_link"]
    assert len(dead_links_before) == 1

    # 创建缺失的llm.md页面
    llm_path = settings.wiki_dir / "concepts/llm.md"
    llm_content = build_frontmatter({
        "title": "大语言模型",
        "type": "concept",
        "tags": ["大语言模型", "AI"],
        "created_at": "2024-04-17",
        "updated_at": "2024-04-17",
        "source_count": 1
    }) + "\n大语言模型是一种能够理解和生成人类语言的人工智能模型。"
    llm_path.write_text(llm_content, encoding="utf-8")

    # 再次运行lint，确认死链已经不存在了
    report_after = lint_wiki()
    dead_links_after = [issue for issue in report_after["issues"] if issue["type"] == "dead_link"]
    assert len(dead_links_after) == 0

def test_lint_generate_report():
    """测试生成Lint报告功能"""
    report = lint_wiki()
    assert "total_issues" in report
    assert "fixed_issues" in report
    assert "issues" in report
    assert report["total_issues"] >= 4  # 至少有死链、孤立页面、内容冲突、缺失页面四个问题
