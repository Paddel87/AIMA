"""Fehlerhierarchie für AIMA-Backends.

VERTRAGSDATEI. Änderungen erfordern explizite User-Freigabe und einen
`[contract]`-PR (siehe CONTRIBUTING.md §6).

Die Hierarchie definiert eine eindeutige Retry-Semantik:
- ``RetriableError`` und Unterklassen → Worker SOLL wiederholen (mit Backoff)
- ``TerminalError`` und Unterklassen → Worker SOLL aufgeben

Backends MÜSSEN diese Klassen verwenden, statt eigene Exception-Typen zu
werfen oder generische ``Exception`` durchzureichen. Die Pipeline-Logik im
Celery-Worker verlässt sich auf diese Unterscheidung.
"""

from __future__ import annotations

from uuid import UUID


class AIMAError(Exception):
    """Basisklasse für alle AIMA-spezifischen Fehler."""

    def __init__(self, message: str, *, request_id: UUID | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.request_id = request_id

    def __str__(self) -> str:
        if self.request_id is None:
            return self.message
        return f"[req={self.request_id}] {self.message}"


class BackendError(AIMAError):
    """Basisklasse für Fehler, die in einem ``AnalysisBackend`` entstehen.

    Trägt den Backend-Namen (z. B. ``"runpod"``, ``"google_ai"``) für
    Logging und Audit. Wird nicht direkt geworfen — stattdessen
    immer eine der konkreten Unterklassen.
    """

    def __init__(
        self,
        message: str,
        *,
        backend_name: str,
        request_id: UUID | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message, request_id=request_id)
        self.backend_name = backend_name
        self.cause = cause

    def __str__(self) -> str:
        prefix = f"[{self.backend_name}]"
        if self.request_id is not None:
            prefix = f"{prefix}[req={self.request_id}]"
        return f"{prefix} {self.message}"


# ---------------------------------------------------------------------------
# Retriable: Worker soll mit Backoff wiederholen.
# ---------------------------------------------------------------------------


class RetriableError(BackendError):
    """Transienter Fehler. Worker SOLL den Aufruf wiederholen.

    Konkrete Auslöser: Netzwerk-Hänger, HTTP 5xx, Cold-Start-Timeout,
    Cloudflare-Block (UA fehlt), unerwartete Verbindungsabbrüche.
    """


class BackendUnavailableError(RetriableError):
    """Backend ist temporär nicht erreichbar.

    Beispiele: Netzwerkfehler, HTTP 502/503/504, RunPod-Endpoint
    antwortet nicht innerhalb des Timeouts während des Cold Starts.
    """


class RateLimitError(RetriableError):
    """Backend hat Quota erreicht (HTTP 429 oder backendseitiges Quota-Signal).

    ``retry_after_seconds`` gibt die empfohlene Wartezeit an, falls
    vom Backend signalisiert (z. B. ``Retry-After``-Header). ``None``
    bedeutet: Worker entscheidet selbst (z. B. exponentielles Backoff).
    """

    def __init__(
        self,
        message: str,
        *,
        backend_name: str,
        retry_after_seconds: float | None = None,
        request_id: UUID | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(
            message,
            backend_name=backend_name,
            request_id=request_id,
            cause=cause,
        )
        self.retry_after_seconds = retry_after_seconds


class TimeoutError(RetriableError):  # noqa: A001 — überschreibt Builtin bewusst
    """Backend hat innerhalb des Timeouts nicht geantwortet.

    Kann beim ersten Call nach Cold Start auftreten und ist dann
    transient. Wiederholtes Auftreten signalisiert ein dauerhaftes
    Problem und muss vom Worker durch Max-Retries begrenzt werden.

    Hinweis: Schattet ``builtins.TimeoutError``. Bei gleichzeitigem
    Bedarf den Builtin als ``builtins.TimeoutError`` importieren.
    """


# ---------------------------------------------------------------------------
# Terminal: Worker soll aufgeben.
# ---------------------------------------------------------------------------


class TerminalError(BackendError):
    """Dauerhafter Fehler. Worker SOLL nicht wiederholen.

    Wiederholung würde dasselbe Ergebnis liefern. Job wird als
    fehlgeschlagen markiert und der Fehler im Audit-Log dokumentiert.
    """


class AuthenticationError(TerminalError):
    """Authentifizierung fehlgeschlagen (HTTP 401/403).

    API-Key falsch, abgelaufen oder Berechtigung fehlt. Erfordert
    Admin-Eingriff (neuen Key in ``.env`` eintragen), kein Retry möglich.
    """


class InvalidInputError(TerminalError):
    """Request war fehlerhaft (HTTP 400, 404, 422).

    Beispiele: ungültiger Endpoint-ID, falsch formatierter Payload,
    Bild zu groß für Modell. Wiederholung mit denselben Daten würde
    erneut fehlschlagen.
    """


class HandlerError(TerminalError):
    """Der Handler im RunPod-Worker hat einen Fehler gemeldet.

    Das ist der Fall, wenn ``status == "FAILED"`` mit einer Fehler-
    nachricht zurückkommt — z. B. Modell konnte Bild nicht verarbeiten,
    OOM auf der GPU, kaputtes Eingabe-Bild.
    """


__all__ = [
    "AIMAError",
    "BackendError",
    "RetriableError",
    "BackendUnavailableError",
    "RateLimitError",
    "TimeoutError",
    "TerminalError",
    "AuthenticationError",
    "InvalidInputError",
    "HandlerError",
]
