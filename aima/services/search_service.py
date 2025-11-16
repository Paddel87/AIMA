import os
from typing import List, Dict

from aima.services.vector_store import init_vector_store, query as vs_query
from aima.config import VECTORSTORE_PATH


def search_scenes(query: str, top_k: int) -> list[dict]:
    client = init_vector_store(VECTORSTORE_PATH)
    collection = client.get_or_create_collection(name="aima_scenes")
    results = vs_query(collection, query, top_k=top_k)
    out: List[Dict] = []
    for scene_id, score, metadata in results:
        out.append({"scene_id": str(scene_id), "score": float(score), "metadata": metadata})
    return out