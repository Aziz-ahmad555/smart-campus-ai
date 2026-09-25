"""Addresses come from settings, not code."""
from backend.api import main


def test_cors_allows_only_the_configured_dashboard(client):
    allowed = main.FRONTEND_ORIGINS[0]
    preflight = {"Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization"}
    ok = client.options("/students", headers={"Origin": allowed, **preflight})
    assert ok.headers.get("access-control-allow-origin") == allowed
    other = client.options("/students", headers={"Origin": "http://evil.example", **preflight})
    assert "access-control-allow-origin" not in other.headers


def test_defaults_match_local_development():
    assert main.FRONTEND_ORIGINS == ["http://localhost:5173"]
    assert (main.RP_ID, main.ORIGIN) == ("localhost", "http://localhost:5173")


def test_no_hard_coded_addresses_left_in_the_backend():
    from tests.conftest import ROOT

    for path in ("backend/api/main.py", "backend/api/auth.py", "backend/tracking/engine.py"):
        source = (ROOT / path).read_text(encoding="utf-8")
        code = "\n".join(line for line in source.splitlines() if "os.getenv(" not in line)
        assert "localhost:5173" not in code and "VideoCapture(0)" not in code, path
