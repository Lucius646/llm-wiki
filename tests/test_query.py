import os
import tempfile
from pathlib import Path
from llmwiki.config import settings
from llmwiki.utils import init_wiki_structure, build_frontmatter
from llmwiki.query import query_wiki

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

def test_query_wiki_basic():
    """测试基础问答功能"""
    answer = query_wiki("什么是RAG技术？", save=False)
    assert "检索增强生成" in answer
    assert "RAG" in answer
    # 必须包含引用
    assert "[检索增强生成(RAG)](concepts/rag.md)" in answer

def test_query_wiki_multiple_references():
    """测试回答包含多个引用来源"""
    answer = query_wiki("OpenAI开发了哪些大语言模型？", save=False)
    assert "GPT-3" in answer
    assert "GPT-4" in answer
    assert "GPT-4o" in answer
    # 必须包含多个引用
    assert "[OpenAI](entities/openai.md)" in answer
    assert "[GPT-4](concepts/gpt-4.md)" in answer

def test_query_wiki_no_result():
    """测试没有相关页面的情况"""
    answer = query_wiki("什么是火星上的人工智能技术？", save=False)
    assert "抱歉，没有找到相关的知识库内容" in answer or "没有足够的相关信息" in answer

def test_query_wiki_save_synthesis():
    """测试保存回答为synthesis页面"""
    # 先查询并保存
    answer = query_wiki("RAG的核心流程是什么？", save=True)
    # 验证synthesis文件存在（默认保存在uncategorized子目录）
    synthesis_files = list((settings.wiki_dir / "synthesis").rglob("*.md"))
    assert len(synthesis_files) >= 1
    # 读取文件内容验证
    synthesis_content = synthesis_files[0].read_text(encoding="utf-8")
    assert "RAG的核心流程" in synthesis_content
    assert "引用来源" in synthesis_content
    assert "[检索增强生成(RAG)](concepts/rag.md)" in synthesis_content
    # 验证索引文件更新
    index_content = settings.index_path.read_text(encoding="utf-8")
    assert "RAG的核心流程" in index_content
    # 验证日志更新
    log_content = settings.log_path.read_text(encoding="utf-8")
    assert "回答问题：RAG的核心流程是什么" in log_content

def test_query_wiki_with_topic():
    """测试指定topic查询"""
    answer = query_wiki("发布时间是什么时候？", save=False, topic="GPT-4")
    assert "2023年3月" in answer
    assert "[GPT-4](concepts/gpt-4.md)" in answer
