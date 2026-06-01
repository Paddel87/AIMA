"""Geteilte Datenklassen für AIMA.

VERTRAGSDATEI. Änderungen erfordern explizite User-Freigabe und einen
`[contract]`-PR (siehe CONTRIBUTING.md §6).

Diese Datei definiert die Datenstrukturen, die zwischen API, Worker und
Analyse-Backends fließen. Alle Modelle sind ``frozen`` (immutable). Wer
Werte verändern möchte, erzeugt eine Kopie via ``model_copy()``.

Designprinzipien:
- Pydantic v2 für Validierung, Serialisierung und Konsistenz mit FastAPI.
- ``model_config = ConfigDict(frozen=True, extra="forbid")``: keine
  versehentlichen Zusatzfelder, keine nachträglichen Mutationen.
- Status-Strings für RunPod sind 1:1 die kanonischen Werte aus der
  RunPod-API. Keine eigene Übersetzungsschicht.
- AIMA-interner ``JobStatus`` ist höher abstrahiert als
  ``RunPodJobStatus``: Ein AIMA-Job kann viele RunPod-Calls auslösen.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ModuleType(StrEnum):
    """Analyse-Module, die in der AIMA-Pipeline existieren.

    Kernmodule (immer aktiv): NSFW, PERSONS, REID, OBJECTS.
    Optionale Module (per Job-Toggle): CONTEXT, DESCRIPTION.
    Internes Pipeline-Modul: FUSION (läuft auf VPS, kein Backend-Call).
    """

    NSFW = "nsfw"
    PERSONS = "persons"
    REID = "reid"
    OBJECTS = "objects"
    CONTEXT = "context"
    DESCRIPTION = "description"
    FUSION = "fusion"


class RunPodJobStatus(StrEnum):
    """Kanonische Job-Status-Strings, wie sie die RunPod-API liefert.

    Werte 1:1 aus der RunPod-Dokumentation übernommen. Keine eigene
    Übersetzung — falls RunPod neue Status einführt, hier ergänzen
    und im RunPodBackend behandeln.
    """

    IN_QUEUE = "IN_QUEUE"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"


class JobStatus(StrEnum):
    """AIMA-interner Job-Status (höher abstrahiert als RunPodJobStatus).

    Ein AIMA-Job durchläuft die fünf Pipeline-Stufen aus KONZEPT §4.1
    und kann dabei viele RunPod-Calls auslösen. Der hier abgebildete
    Status reflektiert die *Pipeline*-Stufe, nicht einzelne Backend-Calls.
    """

    PENDING = "pending"          # Erstellt, noch nicht gestartet
    PREPARING = "preparing"      # Vorverarbeitung läuft (VPS)
    RUNNING = "running"          # Mindestens ein Backend-Call aktiv
    AGGREGATING = "aggregating"  # Semantische Fusion läuft (VPS)
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Geometrie und Frame
# ---------------------------------------------------------------------------


class BoundingBox(BaseModel):
    """Achsenparalleler Rahmen in Bildkoordinaten.

    Ursprung links oben (0, 0). Alle Werte in Pixeln.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    x: int = Field(ge=0, description="Linke Kante in Pixeln")
    y: int = Field(ge=0, description="Obere Kante in Pixeln")
    width: int = Field(gt=0, description="Breite in Pixeln")
    height: int = Field(gt=0, description="Höhe in Pixeln")


class Frame(BaseModel):
    """Ein einzelner Frame oder ein Standbild zur Analyse.

    Aktuell wird der Inhalt ausschließlich als Base64 transportiert.
    KONZEPT §11.2 hält die spätere Erweiterung um Presigned URLs offen;
    diese würde als Vertragsänderung ergänzt.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    frame_id: str = Field(
        min_length=1,
        description="Eindeutig innerhalb eines Jobs (z. B. UUID oder media_id+timestamp)",
    )
    media_file_id: UUID = Field(description="Referenz auf media_files-Eintrag")
    timestamp_ms: int | None = Field(
        default=None,
        ge=0,
        description="Bei Video-Frames: Position in Millisekunden ab Videostart. Bei Standbildern: None.",
    )
    width: int = Field(gt=0, description="Bildbreite in Pixeln")
    height: int = Field(gt=0, description="Bildhöhe in Pixeln")
    mime_type: str = Field(
        description="z. B. 'image/jpeg', 'image/png'",
        pattern=r"^image/[a-zA-Z0-9.+-]+$",
    )
    content_base64: str = Field(
        min_length=1,
        description="Bilddaten als Base64-String (ohne Data-URL-Prefix)",
    )


# ---------------------------------------------------------------------------
# Befunde
# ---------------------------------------------------------------------------


class Detection(BaseModel):
    """Ein einzelner Befund, den ein Modul für einen Frame liefert.

    Beispiele:
    - NSFW: ``label="exposed_genitalia"``, ``confidence=0.91``
    - Personen: ``label="face"``, ``bbox=...``, mit zugehörigem Embedding
    - Objekte: ``label="phone"``, ``bbox=...``

    ``metadata`` ist bewusst offen, um modulspezifische Zusatzfelder
    aufnehmen zu können, ohne den Vertrag bei jeder Modulerweiterung
    anfassen zu müssen.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    frame_id: str = Field(min_length=1)
    module: ModuleType
    label: str = Field(min_length=1, description="Modul-spezifisches Erkennungsergebnis")
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: BoundingBox | None = Field(
        default=None,
        description="Position im Frame, falls verfügbar (NSFW liefert oft keine).",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Frei für modulspezifische Felder. Pflicht-Keys werden NICHT hier abgebildet.",
    )


class PersonEmbedding(BaseModel):
    """Gesichts-Embedding-Vektor für Re-Identifikation.

    Der Vektor wird in pgvector persistiert. ArcFace liefert
    typischerweise 512-dimensionale Vektoren; das wird im Validator
    geprüft, weil falsch dimensionierte Embeddings die Re-ID brechen.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    frame_id: str = Field(min_length=1)
    bbox: BoundingBox = Field(description="Position des Gesichts im Frame")
    vector: list[float] = Field(description="Embedding, typisch 512-dim für ArcFace")
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("vector")
    @classmethod
    def _check_vector_length(cls, v: list[float]) -> list[float]:
        if len(v) not in (128, 256, 512, 1024):
            raise ValueError(
                f"vector length {len(v)} unusual — erwartet werden 128/256/512/1024 "
                "(modellabhängig). Prüfe Backend-Konfiguration."
            )
        return v


# ---------------------------------------------------------------------------
# Backend-Schnittstelle: Request und Result
# ---------------------------------------------------------------------------


class AnalysisRequest(BaseModel):
    """Was an ein ``AnalysisBackend.analyze()`` übergeben wird.

    ``request_id`` ist eine clientseitig generierte UUID. Backends
    MÜSSEN bei Wiederholung mit derselben ``request_id`` dasselbe
    Ergebnis liefern oder einen sauberen Fehler werfen — siehe
    Idempotenz-Anforderung in KONZEPT §11.3.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    request_id: UUID = Field(description="Idempotenz-Schlüssel, vom Worker generiert")
    module: ModuleType
    frames: list[Frame] = Field(
        min_length=1,
        description="Modulweise gebündelt — siehe KONZEPT §11.1 'Batch-Verhalten'",
    )
    options: dict[str, Any] = Field(
        default_factory=dict,
        description="Modulspezifische Optionen (z. B. Konfidenz-Schwellwert)",
    )


class AnalysisResult(BaseModel):
    """Was ``AnalysisBackend.analyze()`` zurückgibt.

    ``request_id`` MUSS mit dem Request-Wert übereinstimmen — sonst
    werfen wir einen ``InvalidInputError`` in der Wrapper-Logik.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    request_id: UUID = Field(description="Spiegelt AnalysisRequest.request_id")
    module: ModuleType
    detections: list[Detection] = Field(default_factory=list)
    embeddings: list[PersonEmbedding] = Field(
        default_factory=list,
        description="Nur bei PERSONS und REID befüllt",
    )
    model_version: str = Field(
        min_length=1,
        description="Image-Tag oder Modell-ID, die das Ergebnis erzeugt hat. Audit-relevant.",
    )
    backend_name: str = Field(
        min_length=1,
        description="z. B. 'runpod', 'google_ai', 'xai'",
    )
    duration_ms: int = Field(
        ge=0,
        description="Bruttodauer des Backend-Calls, gemessen vom AIMA-Client",
    )
    cost_estimate_usd: float | None = Field(
        default=None,
        ge=0.0,
        description="Geschätzte Kosten, falls vom Backend gemeldet (RunPod execution time × Preis)",
    )


__all__ = [
    "ModuleType",
    "RunPodJobStatus",
    "JobStatus",
    "BoundingBox",
    "Frame",
    "Detection",
    "PersonEmbedding",
    "AnalysisRequest",
    "AnalysisResult",
]
