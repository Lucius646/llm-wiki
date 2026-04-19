import tempfile
import os
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock
from llmwiki.config import settings
from llmwiki.utils import init_wiki_structure, build_frontmatter
from llmwiki.vector_search import VectorIndex, get_relevant_pages, VECTOR_SUPPORT

# 如果没有向量支持，跳过所有测试
pytestmark = pytest.mark.skipif(not VECTOR_SUPPORT, reason="Vector search dependencies not installed")

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
        # Page 1: RAG
        {
            "path": settings.wiki_dir / "concepts/rag.md",
            "frontmatter": {
                "title": "检索增强生成",
                "type": "concept",
                "tags": ["大语言模型", "检索", "生成"],
                "created_at": "2024-04-17",
                "updated_at": "2024-04-17",
                "source_count": 1
            },
            "content": """检索增强生成（Retrieval-Augmented Generation，RAG）是一种结合检索系统和大语言模型的技术框架。
它通过在生成回答前先检索外部知识库中的相关信息，能够显著提升回答的准确性、时效性，减少幻觉问题。
核心流程包括：文档索引构建、用户问题理解、相关文档检索、检索结果增强、回答生成五个步骤。"""
        },
        # Page 2: 向量数据库
        {
            "path": settings.wiki_dir / "concepts/vector_database.md",
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
常见的向量数据库包括Pinecone、Chroma、Weaviate、Milvus、FAISS等。"""
        },
        # Page 3: GPT-4
        {
            "path": settings.wiki_dir / "concepts/gpt4.md",
            "frontmatter": {
                "title": "GPT-4",
                "type": "concept",
                "tags": ["大语言模型", "OpenAI"],
                "created_at": "2024-04-17",
                "updated_at": "2024-04-17",
                "source_count": 3
            },
            "content": """GPT-4是OpenAI开发的第四代大语言模型，支持多模态输入，在推理能力上表现出色。
它被广泛应用于聊天机器人、内容生成、代码开发等多个场景，是目前最流行的大语言模型之一。"""
        },
        # Page 4: 大语言模型
        {
            "path": settings.wiki_dir / "concepts/llm.md",
            "frontmatter": {
                "title": "大语言模型",
                "type": "concept",
                "tags": ["AI", "语言模型"],
                "created_at": "2024-04-17",
                "updated_at": "2024-04-17",
                "source_count": 2
            },
            "content": """大语言模型（Large Language Model，LLM）是一种能够理解和生成人类语言的AI模型。
典型代表包括GPT系列、Claude、Llama、Qwen、GLM等，参数规模从数十亿到数千亿不等。"""
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

def test_vector_index_basic():
    """测试向量索引基本功能"""
    index = VectorIndex()
    # 验证路径正确
    assert index.index_path.parent == settings.wiki_root / ".llmwiki"
    assert index.index_path.name == "vectors.json"

@patch('llmwiki.vector_search.SentenceTransformer')
def test_vector_index_build(mock_model_class):
    """测试向量索引构建（Mock模型，不需要实际下载）"""
    # Mock模型返回固定的384维向量
    mock_model = MagicMock()
    mock_model.encode.return_value = [0.1] * 384
    mock_model_class.return_value = mock_model

    index = VectorIndex()
    # 构建索引
    index.build_index()

    # 验证模型被加载
    mock_model_class.assert_called_once_with("all-MiniLM-L6-v2")
    # 验证encode被调用了4次（4个页面）
    assert mock_model.encode.call_count == 4
    # 应该有4个文档
    assert len(index.vectors) == 4
    # 所有路径都存在
    paths = [vec["path"] for vec in index.vectors.values()]
    assert "concepts/rag.md" in paths
    assert "concepts/vector_database.md" in paths
    assert "concepts/gpt4.md" in paths
    assert "concepts/llm.md" in paths
    # 向量维度正确
    first_vec = next(iter(index.vectors.values()))["vector"]
    assert len(first_vec) == 384

@patch('llmwiki.vector_search.SentenceTransformer')
def test_vector_index_save_load(mock_model_class):
    """测试向量索引保存和加载"""
    # Mock模型
    mock_model = MagicMock()
    mock_model.encode.return_value = [0.1] * 384
    mock_model_class.return_value = mock_model

    # 构建并保存索引
    index1 = VectorIndex()
    index1.build_index()
    index1.save_index()

    # 验证文件存在
    assert index1.index_path.exists()

    # 加载索引（不需要模型）
    index2 = VectorIndex()
    index2.load_index()

    # 应该和原来的一致
    assert len(index2.vectors) == 4
    assert index2.vectors.keys() == index1.vectors.keys()

@patch('llmwiki.vector_search.SentenceTransformer')
@patch('llmwiki.vector_search.cosine_similarity')
def test_semantic_search(mock_cosine, mock_model_class):
    """测试语义搜索功能（Mock相似度计算）"""
    # Mock模型
    mock_model = MagicMock()
    mock_model.encode.return_value = [0.1] * 384
    mock_model_class.return_value = mock_model

    # Mock相似度，让第一个结果得分最高，第二个次之，其他低
    mock_cosine.side_effect = [
        [[0.9]],  # rag.md
        [[0.8]],  # vector_database.md
        [[0.3]],  # gpt4.md
        [[0.2]],  # llm.md
    ]

    index = VectorIndex()
    index.build_index()

    # 搜索"检索相关的技术"
    results = index.search("检索相关的技术", top_k=3)

    # 验证调用了encode查询向量
    assert mock_model.encode.call_count == 5  # 4个文档 + 1次查询
    # 验证相似度计算被调用了4次
    assert mock_cosine.call_count == 4
    # 应该返回2个结果（得分>=0.3）
    assert len(results) == 2
    # 得分从高到低排序
    assert results[0]["score"] == 0.9
    assert results[1]["score"] == 0.8

@patch('llmwiki.vector_search.SentenceTransformer')
@patch('llmwiki.vector_search.cosine_similarity')
def test_semantic_search_min_score(mock_cosine, mock_model_class):
    """测试语义搜索最低得分过滤"""
    # Mock模型
    mock_model = MagicMock()
    mock_model.encode.return_value = [0.1] * 384
    mock_model_class.return_value = mock_model

    # Mock所有结果得分都低于0.3
    mock_cosine.return_value = [[0.2]]

    index = VectorIndex()
    index.build_index()

    results = index.search("不存在的内容", min_score=0.3)
    assert len(results) == 0

@patch('llmwiki.vector_search.search_relevant_pages')
@patch('llmwiki.vector_search.SentenceTransformer')
@patch('llmwiki.vector_search.cosine_similarity')
def test_mixed_search(mock_cosine, mock_model_class, mock_keyword_search):
    """测试混合检索（关键词+语义）"""
    # Mock关键词搜索返回结果
    mock_keyword_search.return_value = [
        {"path": "concepts/rag.md", "score": 100, "title": "检索增强生成", "preview": "..."},
        {"path": "concepts/llm.md", "score": 80, "title": "大语言模型", "preview": "..."},
    ]

    # Mock向量搜索
    mock_model = MagicMock()
    mock_model.encode.return_value = [0.1] * 384
    mock_model_class.return_value = mock_model
    mock_cosine.side_effect = [
        [[0.9]],  # rag.md
        [[0.7]],  # vector_database.md
        [[0.8]],  # gpt4.md
        [[0.6]],  # llm.md
    ]

    # 混合检索，语义权重0.5
    results = get_relevant_pages("RAG相关内容", use_semantic=True, limit=3, mix_weight=0.5)

    # 验证调用了两种搜索
    mock_keyword_search.assert_called_once()
    assert mock_model.encode.called
    # 结果应该包含rag、llm、vector_database
    assert len(results) == 3
    # rag得分最高
    assert results[0]["path"] == "concepts/rag.md"

@patch('llmwiki.vector_search.SentenceTransformer')
def test_incremental_update(mock_model_class):
    """测试增量更新索引"""
    # Mock模型
    mock_model = MagicMock()
    mock_model.encode.return_value = [0.1] * 384
    mock_model_class.return_value = mock_model

    index = VectorIndex()
    index.build_index()
    original_count = len(index.vectors)
    assert original_count == 4

    # 新增一个页面
    new_page_path = settings.wiki_dir / "concepts/faiss.md"
    new_content = build_frontmatter({
        "title": "FAISS",
        "type": "concept",
        "tags": ["向量检索", "Facebook"],
        "created_at": "2024-04-17",
        "updated_at": "2024-04-17",
        "source_count": 1
    }) + "\nFAISS是Facebook开发的向量检索库，支持高效的相似度搜索。"
    new_page_path.write_text(new_content, encoding="utf-8")

    # 重置mock计数
    mock_model.encode.reset_mock()

    # 增量更新
    index.update_index()

    # 验证只encode了新增的1个页面
    assert mock_model.encode.call_count == 1
    # 应该多了一个文档
    assert len(index.vectors) == original_count + 1
    # 新页面存在
    assert "concepts/faiss.md" in index.vectors

def test_vector_search_disabled():
    """测试禁用语义搜索时自动降级到关键词搜索"""
    # 当use_semantic=False时，应该直接返回关键词搜索结果
    with patch('llmwiki.vector_search.search_relevant_pages') as mock_keyword:
        mock_keyword.return_value = [{"path": "concepts/rag.md", "score": 100}]
        results = get_relevant_pages("RAG", use_semantic=False)
        mock_keyword.assert_called_once_with("RAG", limit=5)
        assert len(results) == 1
        assert results[0]["path"] == "concepts/rag.md"

@patch('llmwiki.vector_search.SentenceTransformer')
def test_empty_index_automatically_build(mock_model_class):
    """测试空索引时自动构建"""
    # Mock模型
    mock_model = MagicMock()
    mock_model.encode.return_value = [0.1] * 384
    mock_model_class.return_value = mock_model

    index = VectorIndex()
    # 先删除索引文件
    if index.index_path.exists():
        index.index_path.unlink()

    # 搜索时应该自动构建索引
    results = index.search("测试")
    assert len(index.vectors) == 4
