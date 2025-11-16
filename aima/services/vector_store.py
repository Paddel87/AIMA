import os
from typing import Any, Dict, List, Tuple

import chromadb


def init_vector_store(path: str):
    os.makedirs(path, exist_ok=True)
    client = chromadb.PersistentClient(path=path)
    return client


def add_scene(collection, scene_id: str, embedding: list[float], metadata: dict):
    collection.add(ids=[scene_id], embeddings=[embedding], metadatas=[metadata])


def query(collection, text: str, top_k: int = 3):
    from aima.services.embedding_service import embed_texts

    emb = embed_texts([text])[0]
    res = collection.query(query_embeddings=[emb], n_results=top_k, include=["metadatas", "distances"])
    ids = res.get("ids", [[]])[0]
    distances = res.get("distances", [[]])[0]
    metadatas = res.get("metadatas", [[]])[0]
    return [(ids[i], float(distances[i]), metadatas[i]) for i in range(len(ids))]