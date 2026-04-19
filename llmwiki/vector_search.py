import os
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from llmwiki.config import settings
from llmwiki.utils import extract_frontmatter
from llmwiki.search import search_relevant_pages as keyword_search

# 向量依赖是可选的，只有用户安装了才启用
try:
    import numpy as np
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity
    VECTOR_SUPPORT = True
except ImportError:
    VECTOR_SUPPORT = False
    np = None
    SentenceTransformer = None
    cosine_similarity = None

class VectorIndex:
    """
    纯本地离线向量索引，不需要外部数据库
    向量数据存储在 .llmwiki/vectors.json 文件中
    """
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = None
        self.vectors = {}  # key: 文件相对路径, value: {"vector": [...], "last_modified": 时间戳, "title": "页面标题"}
        self.index_path = settings.wiki_root / ".llmwiki" / "vectors.json"
        # 确保.llmwiki目录存在
        (settings.wiki_root / ".llmwiki").mkdir(exist_ok=True)

    def _load_model(self):
        """懒加载模型，只有第一次使用的时候才加载"""
        if not VECTOR_SUPPORT:
            raise RuntimeError("向量检索功能需要安装依赖：pip install sentence-transformers numpy scikit-learn")
        if self.model is None:
            self.model = SentenceTransformer(self.model_name)

    def _get_file_content(self, file_path: Path) -> str:
        """提取文件的文本内容，用于生成向量"""
        try:
            content = file_path.read_text(encoding="utf-8")
            frontmatter, body = extract_frontmatter(content)
            title = frontmatter.get("title", file_path.stem)
            tags = " ".join(frontmatter.get("tags", []))
            # 向量使用标题+标签+前1000字符的正文，足够覆盖主要内容
            return f"{title} {tags} {body[:1000]}"
        except Exception as e:
            print(f"警告：读取文件 {file_path} 失败：{e}")
            return ""

    def build_index(self, force_rebuild: bool = False):
        """
        构建向量索引
        force_rebuild: 强制全量重建，否则只增量更新修改过的文件
        """
        if not VECTOR_SUPPORT:
            return

        self._load_model()

        # 如果索引文件存在且不强制重建，先加载已有索引
        if self.index_path.exists() and not force_rebuild:
            self.load_index()

        # 遍历所有wiki页面
        for root, _, files in os.walk(settings.wiki_dir):
            for file in files:
                if file.endswith(".md") and not file.startswith(".") and file not in ["index.md", "log.md"]:
                    file_path = Path(root) / file
                    rel_path = str(file_path.relative_to(settings.wiki_dir)).replace("\\", "/")
                    last_modified = file_path.stat().st_mtime

                    # 如果文件已经在索引中且没有修改，跳过
                    if rel_path in self.vectors and self.vectors[rel_path]["last_modified"] >= last_modified:
                        continue

                    # 生成向量
                    content = self._get_file_content(file_path)
                    if not content:
                        continue

                    vector = self.model.encode(content).tolist()
                    frontmatter, _ = extract_frontmatter(file_path.read_text(encoding="utf-8"))

                    self.vectors[rel_path] = {
                        "vector": vector,
                        "last_modified": last_modified,
                        "title": frontmatter.get("title", file_path.stem),
                        "type": frontmatter.get("type", "concept")
                    }

        # 保存索引
        self.save_index()

    def update_index(self):
        """增量更新索引，等同于build_index(force_rebuild=False)"""
        self.build_index(force_rebuild=False)

    def save_index(self):
        """保存向量索引到本地文件"""
        if not VECTOR_SUPPORT:
            return

        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(self.vectors, f, ensure_ascii=False, indent=2)

    def load_index(self):
        """从本地文件加载向量索引"""
        if not VECTOR_SUPPORT:
            return

        if self.index_path.exists():
            with open(self.index_path, "r", encoding="utf-8") as f:
                self.vectors = json.load(f)

    def search(self, query: str, top_k: int = 5, min_score: float = 0.3) -> List[Dict[str, Any]]:
        """
        语义搜索相关页面
        返回结果格式：[{"path": "页面相对路径", "title": "页面标题", "score": 相似度得分（0-1）, "type": "页面类型"}]
        """
        if not VECTOR_SUPPORT or not self.vectors:
            return []

        self._load_model()

        # 生成查询向量
        query_vector = self.model.encode(query).reshape(1, -1)
        results = []

        # 计算相似度
        for path, data in self.vectors.items():
            vector = np.array(data["vector"]).reshape(1, -1)
            similarity = cosine_similarity(query_vector, vector)[0][0]

            if similarity >= min_score:
                results.append({
                    "path": path,
                    "title": data["title"],
                    "score": float(similarity),
                    "type": data.get("type", "concept")
                })

        # 按得分排序
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

def get_relevant_pages(query: str, use_semantic: bool = True, limit: int = 5, mix_weight: float = 0.5) -> List[Dict[str, Any]]:
    """
    混合检索：结合关键词检索和语义检索的结果
    mix_weight: 语义检索的权重，0-1，越大语义占比越高
    """
    # 如果关闭语义或者没有向量支持，直接返回关键词搜索结果
    if not use_semantic or not VECTOR_SUPPORT:
        return keyword_search(query, limit=limit)

    # 1. 关键词检索
    keyword_results = keyword_search(query, limit=limit * 2)
    # 转换格式，统一得分到0-1区间
    keyword_map = {}
    max_keyword_score = max([res["score"] for res in keyword_results]) if keyword_results else 0
    for res in keyword_results:
        normalized_score = res["score"] / max_keyword_score if max_keyword_score > 0 else 0
        keyword_map[res["path"]] = {**res, "score": normalized_score}

    # 2. 语义检索
    vector_index = VectorIndex()
    vector_index.load_index()
    # 如果没有索引，先构建
    if not vector_index.vectors:
        vector_index.build_index()
    semantic_results = vector_index.search(query, top_k=limit * 2)
    semantic_map = {res["path"]: res for res in semantic_results}

    # 3. 合并结果
    all_paths = set(keyword_map.keys()).union(set(semantic_map.keys()))
    combined_results = []

    for path in all_paths:
        keyword_data = keyword_map.get(path)
        semantic_data = semantic_map.get(path)

        # 计算综合得分
        keyword_score = keyword_data["score"] if keyword_data else 0
        semantic_score = semantic_data["score"] if semantic_data else 0
        final_score = (keyword_score * (1 - mix_weight)) + (semantic_score * mix_weight)

        # 取更完整的元数据
        if keyword_data:
            data = keyword_data.copy()
        else:
            # 如果只有语义结果，需要补全内容和预览
            file_path = settings.wiki_dir / path
            content = file_path.read_text(encoding="utf-8")
            frontmatter, body = extract_frontmatter(content)
            preview = body[:200].replace("\n", " ").strip()
            if len(preview) > 200:
                preview = preview[:197] + "..."
            data = {
                "title": frontmatter.get("title", Path(path).stem),
                "path": path,
                "full_path": str(file_path),
                "preview": preview,
                "content": content,
                "frontmatter": frontmatter
            }

        data["score"] = final_score
        data["keyword_score"] = keyword_score
        data["semantic_score"] = semantic_score
        combined_results.append(data)

    # 按综合得分排序
    combined_results.sort(key=lambda x: x["score"], reverse=True)
    return combined_results[:limit]
