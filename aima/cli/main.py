import os
import json
from typing import List

import typer

from aima.pipelines.analyzer import analyze_video
from aima.services.search_service import search_scenes
from aima.services.person_service import run_person_clustering
from aima import config


app = typer.Typer()
persons_app = typer.Typer()
app.add_typer(persons_app, name="persons")


@app.command()
def analyze(
    video_path: str,
    duration: float = typer.Option(...),
    modules: str = typer.Option("objects,asr"),
    out: str = typer.Option("outputs"),
):
    os.makedirs(out, exist_ok=True)
    modules_list: List[str] = [m.strip() for m in modules.split(",") if m.strip()]
    vid = analyze_video(video_path, duration, modules_list, out)
    print(f"video_id={vid} output_dir={os.path.join(out, vid)}")

@app.command()
def search(query: str, top_k: int = typer.Option(3, "--top_k"), video: str = typer.Option(None, "--video")):
    results = search_scenes(query, top_k)
    for r in results:
        if video and r["video_id"] != video:
            continue
        print(f"video_id={r['video_id']} scene_id={r['scene_id']} score={r['score']}")
        json_path = os.path.join("outputs", r["video_id"], "scenes", f"scene_{r['scene_id']}.json")
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                print(f.read())

@persons_app.command()
def cluster(
    update_scenes: bool = typer.Option(False, "--update-scenes"),
    method: str = typer.Option(None, "--method"),
    eps: float = typer.Option(None, "--eps"),
    min_samples: int = typer.Option(None, "--min-samples"),
):
    if method is not None:
        config.PERSONS_CLUSTERING_METHOD = method
    if eps is not None:
        config.PERSONS_DBSCAN_EPS = eps
    if min_samples is not None:
        config.PERSONS_DBSCAN_MIN_SAMPLES = min_samples
    res = run_person_clustering(config.OUTPUTS_PATH, update_scenes)
    print(json.dumps(res, ensure_ascii=False))

if __name__ == "__main__":
    app()