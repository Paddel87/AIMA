from typing import List

from ultralytics import YOLO

from aima.schemas.models import DetectedObject


def detect_objects(image_path: str, threshold: float = 0.6) -> list[DetectedObject]:
    model = YOLO("yolov8n.pt")
    results = model(image_path)
    dets: List[DetectedObject] = []
    if not results:
        return dets
    r = results[0]
    boxes = r.boxes
    if boxes is None:
        return dets
    xyxy = boxes.xyxy.cpu().numpy().tolist()
    conf = boxes.conf.cpu().numpy().tolist()
    cls = boxes.cls.cpu().numpy().tolist()
    names = model.names
    for i in range(len(xyxy)):
        if float(conf[i]) < threshold:
            continue
        c = int(cls[i])
        dets.append(
            DetectedObject(
                class_name=str(names.get(c, str(c))),
                confidence=float(conf[i]),
                bbox=[float(v) for v in xyxy[i]],
            )
        )
    return dets