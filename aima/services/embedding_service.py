from sentence_transformers import SentenceTransformer

_model = SentenceTransformer("all-MiniLM-L6-v2")


def embed_texts(texts: list[str]) -> list[list[float]]:
    embeddings = _model.encode(texts, normalize_embeddings=True)
    return [list(map(float, e)) for e in embeddings]