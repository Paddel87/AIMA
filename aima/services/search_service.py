import os
from typing import List, Dict

from aima.services.vector_store import init_vector_store, query as vs_query
from aima.config import GLOBAL_VECTORSTORE_PATH


def search_scenes(query: str, top_k: int) -> list[dict]:
    client = init_vector_store(GLOBAL_VECTORSTORE_PATH)
    collection = client.get_or_create_collection(name="aima_scenes")
    results = vs_query(collection, query, top_k=top_k)
    out: List[Dict] = []
    for scene_id, score, metadata in results:
        md = dict(metadata)
        tags_str = md.get("tags", "")
        md["tags"] = [t for t in tags_str.split(",") if t]
        out.append({
            "video_id": md.get("video_id", ""),
            "scene_id": int(md.get("scene_id", 0)),
            "score": float(score),
            "metadata": md,
        })
    return out