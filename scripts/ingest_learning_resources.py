#!/usr/bin/env python3
"""
学习资源向量化入库脚本

功能:
- 从 data/learning_resources/learning_resources.json 读取资源
- 字段规范化与同义词归一
- 生成嵌入并 upsert 到 ChromaDB 的 learning_resources 集合
- 可选: 按 source 清理本批次未出现的旧资源(下线)

用法:
  python scripts/ingest_learning_resources.py \
    --path data/learning_resources/learning_resources.json \
    --source user_json_v1 --version 20250820 --remove-stale
"""
import os
import json
import hashlib
import argparse
from typing import List, Dict, Any

from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings


CHROMA_DIR = os.getenv("CHROMA_PERSIST_DIRECTORY", "./data/chroma_db")
COLLECTION_NAME = "learning_resources"

# 能力维度归一映射(与后端推荐/评估一致)
COMPETENCY_ALIAS = {
    "expression_ability": "communication_ability",
    "stress_resistance": "stress_resilience",
}


def normalize_competency(value: str) -> str:
    value = (value or "").strip()
    return COMPETENCY_ALIAS.get(value, value)


def make_stable_id(resource: Dict[str, Any]) -> str:
    if resource.get("id"):
        return str(resource["id"])  # 保留外部ID
    base = f"{resource.get('title','')}|{resource.get('url','')}"
    h = hashlib.sha1(base.encode("utf-8")).hexdigest()
    return f"lr_{h[:24]}"


def load_resources(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        if isinstance(data, list):
            return data
        raise ValueError("JSON 格式应为数组(list)")


def build_doc_and_meta(raw: Dict[str, Any], source: str, version: str) -> (str, Dict[str, Any]):
    # keywords 兼容数组/字符串
    keywords = raw.get("keywords", "")
    if isinstance(keywords, list):
        keywords = ",".join([str(x) for x in keywords])

    competency = normalize_competency(raw.get("competency")) or "professional_knowledge"

    metadata = {
        "title": raw.get("title", ""),
        "description": raw.get("description", ""),
        "url": raw.get("url", ""),
        "type": (raw.get("type", "article") or "article").lower(),
        "competency": competency,
        "difficulty": (raw.get("difficulty", "beginner") or "beginner").lower(),
        "field": raw.get("field", ""),
        "keywords": keywords,
        "image": raw.get("image") or raw.get("Image") or "",
        "source": source,
        "version": version,
    }

    # 向量文本: 标题 + 描述 + 关键词
    document_text = f"{metadata['title']} {raw.get('description','')} {keywords}".strip()

    return document_text, metadata


def upsert_resources(path: str, source: str, version: str, remove_stale: bool = False) -> None:
    client = chromadb.PersistentClient(
        path=CHROMA_DIR,
        settings=Settings(allow_reset=True, anonymized_telemetry=False),
    )

    try:
        collection = client.get_collection(COLLECTION_NAME)
    except Exception:
        collection = client.create_collection(
            name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
        )

    encoder = SentenceTransformer("all-MiniLM-L6-v2")

    raw_list = load_resources(path)
    ids: List[str] = []
    docs: List[str] = []
    metas: List[Dict[str, Any]] = []

    for raw in raw_list:
        rid = make_stable_id(raw)
        doc, meta = build_doc_and_meta(raw, source, version)
        ids.append(rid)
        docs.append(doc)
        metas.append(meta)

    embeddings = encoder.encode(docs).tolist()

    # upsert: 存在则覆盖, 不存在则新增
    collection.upsert(ids=ids, documents=docs, metadatas=metas, embeddings=embeddings)

    removed = 0
    if remove_stale:
        existing = collection.get(where={"source": {"$eq": source}})
        exist_ids = set(existing.get("ids", []) or [])
        keep = set(ids)
        to_delete = list(exist_ids - keep)
        if to_delete:
            collection.delete(ids=to_delete)
            removed = len(to_delete)

    print(f"✅ Upsert {len(ids)} 条资源到 '{COLLECTION_NAME}'；清理下线 {removed} 条；源: {source}, 版本: {version}")


def main():
    parser = argparse.ArgumentParser(description="学习资源向量化入库")
    parser.add_argument("--path", default="data/learning_resources/learning_resources.json", help="资源JSON路径")
    parser.add_argument("--source", default="user_json_v1", help="数据来源标签")
    parser.add_argument("--version", default="v1", help="版本号/批次号")
    parser.add_argument("--remove-stale", action="store_true", help="是否删除本来源中未出现的旧资源")
    args = parser.parse_args()

    upsert_resources(args.path, args.source, args.version, args.remove_stale)


if __name__ == "__main__":
    main()


