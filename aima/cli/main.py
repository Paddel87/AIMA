import os
from typing import List

import typer

from aima.pipelines.analyzer import analyze_video
from aima.services.embedding_service import embed_texts
from aima.services.vector_store import init_vector_store, query as vs_query


app = typer.Typer()


@app.command()
def analyze(
    video_path: str,
    duration: float = typer.Option(...),
    modules: str = typer.Option("objects,asr"),
    out: str = typer.Option("outputs"),
):
    os.makedirs(out, exist_ok=True)
    os.makedirs(os.path.join(out, "frames"), exist_ok=True)
    modules_list: List[str] = [m.strip() for m in modules.split(",") if m.strip()]
    analyze_video(video_path, duration, modules_list, out)

@app.command()
def search(query: str, top_k: int = typer.Option(3, "--top_k")):
    vs_path = os.path.join("outputs", "vectorstore")
    client = init_vector_store(vs_path)
    collection = client.get_or_create_collection(name="aima_scenes")
    results = vs_query(collection, query, top_k=top_k)
    for scene_id, score, meta in results:
        print(f"scene_id={scene_id} score={score}")
        json_path = os.path.join("outputs", f"scene_{scene_id}.json")
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                print(f.read())

if __name__ == "__main__":
    app()