import os
import json
from typing import List, Dict, Tuple
import numpy as np
from sklearn.cluster import DBSCAN, AgglomerativeClustering
from aima import config


def _list_scene_jsons(outputs_path: str) -> List[str]:
    paths: List[str] = []
    if not os.path.exists(outputs_path):
        return paths
    for vid in os.listdir(outputs_path):
        base = os.path.join(outputs_path, vid, "scenes")
        if not os.path.isdir(base):
            continue
        for fn in os.listdir(base):
            if fn.endswith(".json"):
                paths.append(os.path.join(base, fn))
    return paths


def _collect_faces(outputs_path: str) -> List[Dict]:
    faces: List[Dict] = []
    for p in _list_scene_jsons(outputs_path):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        scene = data.get("scene", {})
        video_id = scene.get("video_id")
        scene_id = scene.get("id")
        fitems = data.get("faces") or []
        for fi in fitems:
            emb = fi.get("embedding")
            face_id = fi.get("face_id")
            if isinstance(emb, list) and len(emb) > 0 and face_id:
                faces.append(
                    {
                        "face_id": face_id,
                        "embedding": emb,
                        "confidence": fi.get("confidence"),
                        "bbox": fi.get("bbox"),
                        "video_id": video_id,
                        "scene_id": scene_id,
                        "scene_path": p,
                    }
                )
    return faces


def _cluster(embeddings: np.ndarray, method: str, eps: float, min_samples: int) -> np.ndarray:
    if embeddings.size == 0:
        return np.array([], dtype=int)
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    X = embeddings / norms
    if method == "agglomerative":
        model = AgglomerativeClustering(n_clusters=None, distance_threshold=eps, linkage="average")
        labels = model.fit_predict(X)
    else:
        model = DBSCAN(eps=eps, min_samples=min_samples, metric="cosine")
        labels = model.fit_predict(X)
    return labels


def _aggregate(faces: List[Dict], labels: np.ndarray) -> Tuple[List[Dict], Dict[str, str]]:
    mapping: Dict[str, str] = {}
    persons: Dict[int, List[Dict]] = {}
    for i, f in enumerate(faces):
        lab = int(labels[i]) if i < len(labels) else -1
        if lab < 0:
            continue
        persons.setdefault(lab, []).append(f)
    result: List[Dict] = []
    for idx, arr in persons.items():
        pid = f"person_{idx}"
        vids = {a["video_id"] for a in arr if a.get("video_id") is not None}
        scs = {(a.get("video_id"), a.get("scene_id")) for a in arr}
        rep = max(arr, key=lambda a: float(a.get("confidence") or 0.0))
        for a in arr:
            mapping[a["face_id"]] = pid
        result.append(
            {
                "person_id": pid,
                "num_faces": len(arr),
                "num_scenes": len(scs),
                "num_videos": len(vids),
                "representative_face_id": rep.get("face_id"),
                "representative_confidence": float(rep.get("confidence") or 0.0),
                "faces": [
                    {
                        "face_id": a.get("face_id"),
                        "video_id": a.get("video_id"),
                        "scene_id": a.get("scene_id"),
                        "confidence": a.get("confidence"),
                        "bbox": a.get("bbox"),
                    }
                    for a in arr
                ],
            }
        )
    return result, mapping


def _persist(outputs_path: str, persons: List[Dict], mapping: Dict[str, str]) -> None:
    persons_dir = os.path.join(outputs_path, "persons")
    os.makedirs(persons_dir, exist_ok=True)
    with open(os.path.join(persons_dir, "persons.json"), "w", encoding="utf-8") as f:
        json.dump(persons, f, ensure_ascii=False, indent=2)
    with open(os.path.join(persons_dir, "face_person_map.json"), "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)


def _update_scenes(mapping: Dict[str, str], faces: List[Dict]) -> None:
    by_scene: Dict[str, List[Tuple[str, str]]] = {}
    for f in faces:
        sp = f.get("scene_path")
        fid = f.get("face_id")
        pid = mapping.get(fid)
        if sp and pid:
            by_scene.setdefault(sp, []).append((fid, pid))
    for sp, pairs in by_scene.items():
        try:
            with open(sp, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        fl = data.get("faces") or []
        changed = False
        for fi in fl:
            fid = fi.get("face_id")
            for pfid, pid in pairs:
                if fid == pfid:
                    fi["person_id"] = pid
                    changed = True
        if changed:
            with open(sp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)


def run_person_clustering(outputs_path: str | None = None, update_scenes: bool | None = None) -> Dict:
    outp = outputs_path or config.OUTPUTS_PATH
    faces = _collect_faces(outp)
    if not faces:
        persons = []
        mapping = {}
        _persist(outp, persons, mapping)
        return {"persons": persons, "mapping_size": 0}
    embeddings = np.array([f["embedding"] for f in faces], dtype=float)
    method = config.PERSONS_CLUSTERING_METHOD
    eps = float(config.PERSONS_DBSCAN_EPS)
    min_samples = int(config.PERSONS_DBSCAN_MIN_SAMPLES)
    labels = _cluster(embeddings, method, eps, min_samples)
    persons, mapping = _aggregate(faces, labels)
    _persist(outp, persons, mapping)
    upd = config.PERSONS_UPDATE_SCENES if update_scenes is None else update_scenes
    if upd:
        _update_scenes(mapping, faces)
    return {"persons": persons, "mapping_size": len(mapping)}