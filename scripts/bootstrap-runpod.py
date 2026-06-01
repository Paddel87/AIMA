"""Bootstrap-Skript fuer RunPod-Serverless-Endpoints (AIMA).

SKELETT — Phase 0. Enthaelt nur das CLI-Geruest. Die eigentliche
Provisionierungs-Logik (Volume -> Template -> Endpoint via RunPod-API,
Idempotenz, Tear-down, Best-Effort-Rollback) wird in Phase 3 ergaenzt
(siehe FAHRPLAN Phase 3 und KONZEPT §11.1).

Dieses Skript ist ein reines Admin-Werkzeug fuer die Kommandozeile. Es wird
NIEMALS vom AIMA-Backend zur Laufzeit aufgerufen und hat keinen Trigger
ueber UI oder API (siehe CLAUDE.md §3, FAHRPLAN Post-MVP-Sperre,
KONZEPT §4.3). Endpoints werden bewusst manuell provisioniert.

Verwendung (ab Phase 3):
    python scripts/bootstrap-runpod.py --status
    python scripts/bootstrap-runpod.py --create nsfw
    python scripts/bootstrap-runpod.py --create-all
    python scripts/bootstrap-runpod.py --teardown persons
    python scripts/bootstrap-runpod.py --teardown-all
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

# Sensible Analyse-Module, die ueber RunPod-Serverless laufen (KONZEPT §4.2).
# Kontext/Bildbeschreibung laufen ueber Google AI / xAI, nicht ueber RunPod.
RUNPOD_MODULES: tuple[str, ...] = ("nsfw", "persons", "reid", "objects")

# Default-Skalierungsparameter pro Endpoint (KONZEPT §11.1).
# Hier nur als Referenz dokumentiert; angewendet wird das erst in Phase 3.
DEFAULT_SCALING: dict[str, object] = {
    "workersMin": 0,
    "workersMax": 1,
    "idleTimeout": 5,
    "flashboot": True,
    "scalerType": "QUEUE_DELAY",
    "scalerValue": 4,
}

_PHASE3_HINT = (
    "Noch nicht implementiert. Die Provisionierung wird in Phase 3 ergaenzt "
    "(siehe FAHRPLAN Phase 3)."
)


def create_endpoint(module: str) -> int:
    """Legt einen Serverless-Endpoint fuer ein Modul an (Phase 3)."""
    print(f"[bootstrap-runpod] --create {module}: {_PHASE3_HINT}")
    return 1


def create_all() -> int:
    """Legt Endpoints fuer alle RunPod-Module an (Phase 3)."""
    print(f"[bootstrap-runpod] --create-all ({', '.join(RUNPOD_MODULES)}): {_PHASE3_HINT}")
    return 1


def teardown_endpoint(module: str) -> int:
    """Raeumt den Endpoint eines Moduls vollstaendig ab (Phase 3)."""
    print(f"[bootstrap-runpod] --teardown {module}: {_PHASE3_HINT}")
    return 1


def teardown_all() -> int:
    """Raeumt alle Endpoints vollstaendig ab (Phase 3)."""
    print(f"[bootstrap-runpod] --teardown-all: {_PHASE3_HINT}")
    return 1


def status() -> int:
    """Zeigt den Status der konfigurierten Endpoints (Phase 3)."""
    print(f"[bootstrap-runpod] --status: {_PHASE3_HINT}")
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bootstrap-runpod",
        description=(
            "Provisioniert und entfernt RunPod-Serverless-Endpoints fuer AIMA "
            "(Admin-Werkzeug, nur manuell). SKELETT — Logik folgt in Phase 3."
        ),
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--create",
        metavar="MODUL",
        choices=RUNPOD_MODULES,
        help=f"Endpoint fuer ein Modul anlegen. Auswahl: {', '.join(RUNPOD_MODULES)}",
    )
    group.add_argument(
        "--create-all",
        action="store_true",
        help="Endpoints fuer alle RunPod-Module anlegen.",
    )
    group.add_argument(
        "--teardown",
        metavar="MODUL",
        choices=RUNPOD_MODULES,
        help="Endpoint eines Moduls vollstaendig abraeumen.",
    )
    group.add_argument(
        "--teardown-all",
        action="store_true",
        help="Alle Endpoints vollstaendig abraeumen.",
    )
    group.add_argument(
        "--status",
        action="store_true",
        help="Status der konfigurierten Endpoints anzeigen.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.create is not None:
        return create_endpoint(args.create)
    if args.create_all:
        return create_all()
    if args.teardown is not None:
        return teardown_endpoint(args.teardown)
    if args.teardown_all:
        return teardown_all()
    if args.status:
        return status()
    parser.error("Keine Aktion angegeben.")


if __name__ == "__main__":
    sys.exit(main())
