from typing import List, Tuple

import easyocr

from aima.config import OCR_LANGUAGES, OCR_MIN_CONFIDENCE, OCR_MAX_TEXT_LENGTH
from aima.schemas.models import OcrBlock

_reader = None


def _get_reader():
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(OCR_LANGUAGES, gpu=False)
    return _reader


def perform_ocr(image_path: str) -> Tuple[str | None, List[OcrBlock] | None]:
    try:
        reader = _get_reader()
        results = reader.readtext(image_path, detail=1)
        blocks: List[OcrBlock] = []
        texts: List[str] = []
        for item in results:
            bbox_pts, text, conf = item
            if not text or float(conf) < float(OCR_MIN_CONFIDENCE):
                continue
            xs = [int(p[0]) for p in bbox_pts]
            ys = [int(p[1]) for p in bbox_pts]
            x1, y1 = min(xs), min(ys)
            x2, y2 = max(xs), max(ys)
            blocks.append(OcrBlock(text=text.strip(), confidence=float(conf), bbox=[x1, y1, x2, y2]))
            texts.append(text.strip())
        if not texts:
            return None, []
        joined = " ".join(texts)
        if len(joined) > OCR_MAX_TEXT_LENGTH:
            joined = joined[: OCR_MAX_TEXT_LENGTH]
        return joined, blocks
    except Exception:
        return None, None