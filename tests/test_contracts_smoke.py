"""Setup-Smoke-Test: Verträge sind importierbar (kein Fachcode)."""

from backend.backends import base
from backend.shared import errors, types


def test_contract_modules_import() -> None:
    assert types.ModuleType.NSFW
    assert issubclass(errors.RetriableError, errors.BackendError)
    assert hasattr(base, "AnalysisBackend")
