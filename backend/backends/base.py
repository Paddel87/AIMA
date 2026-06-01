"""Abstrakte Basis für Analyse-Backends.

VERTRAGSDATEI. Änderungen erfordern explizite User-Freigabe und einen
`[contract]`-PR (siehe CONTRIBUTING.md §6).

Alle Analyse-Backends (RunPod, Google AI, xAI) implementieren das hier
definierte Interface. Die Pipeline-Logik im Celery-Worker programmiert
ausschließlich gegen diesen Vertrag — konkrete Backend-Klassen werden
zur Laufzeit über Konfiguration ausgewählt.

Vertragsregeln, die jede Implementierung einhalten MUSS:

1. **Fehlersemantik.** Bei transienten Fehlern wird ``RetriableError``
   (oder eine Unterklasse) geworfen — der Worker wiederholt mit Backoff.
   Bei dauerhaften Fehlern wird ``TerminalError`` (oder Unterklasse)
   geworfen — der Worker gibt auf. Backends werfen NIEMALS generische
   ``Exception`` oder ``RuntimeError`` nach außen.

2. **Idempotenz.** Mehrfache Aufrufe mit derselben
   ``AnalysisRequest.request_id`` liefern dasselbe Ergebnis oder werfen
   einen sauberen Fehler. Backends, die das nicht garantieren können,
   müssen das in ihrer Dokumentation klar benennen.

3. **Keine autonomen Calls.** Eine ``analyze()``-Implementierung ruft
   das externe Backend genau dann auf, wenn sie selbst aufgerufen wird.
   Kein Pre-Fetching, kein Hintergrund-Polling, keine spekulativen
   Warmup-Calls.

4. **Vollständiger Payload vor Call.** Backends bereiten ihre Requests
   VPS-seitig vollständig vor und schicken erst dann den Call ab — siehe
   KONZEPT §4.1 zur VPS/RunPod-Trennung und §11.6 zur Kostendisziplin.

5. **Synchron.** Die Methoden sind blockierend. Async-Wrapper können
   später ergänzt werden, sind aber nicht Teil dieses Vertrags.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.shared.types import AnalysisRequest, AnalysisResult, ModuleType


class AnalysisBackend(ABC):
    """Abstrakte Basis für Analyse-Backends.

    Implementierungen siehe ``backend/backends/runpod.py``,
    ``backend/backends/google_ai.py``, ``backend/backends/xai.py``.

    Konstruktor-Signaturen unterscheiden sich je Backend (RunPod braucht
    Endpoint-ID, Google AI braucht API-Key, etc.) — daher kein
    abstrakter ``__init__`` hier. Die Backends werden im Worker
    instanziiert und gegen dieses Interface verwendet.
    """

    # ------------------------------------------------------------------
    # Identifikation
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def name(self) -> str:
        """Eindeutiger Backend-Name, kleingeschrieben, ohne Sonderzeichen.

        Wandert in ``AnalysisResult.backend_name`` und ins Audit-Log.
        Beispiele: ``"runpod"``, ``"google_ai"``, ``"xai"``.
        """

    @abstractmethod
    def supports(self, module: ModuleType) -> bool:
        """True, wenn dieses Backend das gegebene Modul ausführen kann.

        Beispiele:
        - RunPod: True für NSFW, PERSONS, REID, OBJECTS
        - Google AI: True für CONTEXT, DESCRIPTION
        - xAI: True für CONTEXT, DESCRIPTION

        Wird vom Worker beim Dispatch geprüft. Ein Backend darf NIE
        eine Anfrage für ein nicht unterstütztes Modul annehmen, sondern
        wirft in ``analyze()`` einen ``InvalidInputError``.
        """

    # ------------------------------------------------------------------
    # Hauptmethode
    # ------------------------------------------------------------------

    @abstractmethod
    def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        """Führt die Analyse für einen vorbereiteten Request aus.

        Die Implementierung MUSS:
        - die ``request_id`` 1:1 in das ``AnalysisResult`` übernehmen
        - das ``module`` aus dem Request unterstützen (siehe ``supports``)
        - den vollständigen Payload zum Backend senden — keine
          Datenakquise erst auf der GPU-Seite
        - ``model_version`` mit der konkreten Modell- oder Image-Version
          füllen, mit der das Ergebnis produziert wurde (Audit)

        Raises:
            BackendUnavailableError: Netzwerkfehler, 5xx, Cold-Start-Hänger
            RateLimitError: 429 oder backendseitiges Quota-Signal
            TimeoutError: Backend antwortet nicht im erwarteten Zeitfenster
            AuthenticationError: Credentials ungültig oder abgelaufen
            InvalidInputError: Request fehlerhaft oder Modul nicht unterstützt
            HandlerError: Backend hat den Job mit ``FAILED`` zurückgegeben

        Wirft NIEMALS generische ``Exception`` oder ``RuntimeError``.
        Unerwartete Fehler müssen in einen passenden Vertragsfehler
        gewrappt werden.
        """

    # ------------------------------------------------------------------
    # Health-Check
    # ------------------------------------------------------------------

    @abstractmethod
    def health_check(self) -> bool:
        """Prüft, ob das Backend erreichbar ist.

        WICHTIG: Diese Methode darf KEINEN Worker starten und KEINE
        GPU-Sekunden verursachen. Für RunPod heißt das: nur die
        ``GET /v2/{endpoint_id}/health``-Route, keine ``/run``- oder
        ``/runsync``-Calls.

        Bei einem unerreichbaren Backend wird ``False`` zurückgegeben,
        NICHT eine Exception geworfen. Diese Methode ist für Monitoring
        gedacht und soll nicht selbst die Pipeline brechen.

        Returns:
            True, wenn das Backend antwortet und grundsätzlich
            arbeitsbereit ist (Worker-Zahlen müssen nicht > 0 sein —
            ``workersMin: 0`` ist erlaubter Normalzustand).
        """


__all__ = ["AnalysisBackend"]
