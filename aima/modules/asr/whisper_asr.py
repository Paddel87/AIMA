import whisper

from aima.schemas.models import AudioSegment


def transcribe_audio(video_path: str) -> list[AudioSegment]:
    model = whisper.load_model("small")
    result = model.transcribe(video_path)
    segments = result.get("segments", [])
    return [
        AudioSegment(start_s=float(seg["start"]), end_s=float(seg["end"]), text=str(seg["text"]))
        for seg in segments
    ]