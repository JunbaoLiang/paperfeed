"""The API Docker image ships only packages/ + services/ — any import of
pipelines.* from services/api works locally but 500s in production. This
tripwire keeps that class of bug out (it happened once: /external-read).
"""

import re
from pathlib import Path

API_ROOT = Path(__file__).resolve().parent.parent / "services" / "api"
IMPORT_RE = re.compile(r"^\s*(from|import)\s+pipelines\b", re.MULTILINE)


def test_api_never_imports_pipelines():
    offenders = [
        str(path)
        for path in API_ROOT.rglob("*.py")
        if IMPORT_RE.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == [], f"services/api must not import pipelines.*: {offenders}"
