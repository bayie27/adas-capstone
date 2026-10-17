from datetime import UTC, datetime
from types import SimpleNamespace

import sqlmodel
from app.maintenance import cli


def test_restart_parser_accepts_tls_health_probe_options():
    args = cli.build_parser().parse_args(
        [
            "restart",
            "--phase",
            "wait",
            "--health-url",
            "https://127.0.0.1:8000/healthz/ready",
            "--health-ca-cert",
            "certs/adas-cert.pem",
        ]
    )

    assert args.health_url == "https://127.0.0.1:8000/healthz/ready"
    assert args.health_ca_cert == "certs/adas-cert.pem"


def test_wait_readiness_uses_the_supplied_ca_for_https(monkeypatch, tmp_path):
    calls = []
    context = object()

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def fake_urlopen(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def exec(self, _statement):
            return self

        def first(self):
            return SimpleNamespace(last_heartbeat_at=datetime.now(UTC))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("ssl.create_default_context", lambda *, cafile: context)
    monkeypatch.setattr(sqlmodel, "Session", lambda _engine: FakeSession())
    monkeypatch.setattr(sqlmodel, "create_engine", lambda _url: object())
    monkeypatch.setattr(
        cli, "resolve_sqlite_db_path", lambda _url: tmp_path / "adas.db"
    )
    monkeypatch.setattr("app.core.db.install_sqlite_pragmas", lambda *_args: None)

    settings = SimpleNamespace(
        DATABASE_URL="sqlite:///adas.db",
        SQLITE_BUSY_TIMEOUT_MS=1000,
        HEARTBEAT_STALE_SECONDS=10,
    )

    result = cli._wait_for_restart_readiness(
        settings,
        timeout=1,
        require_heartbeat=True,
        health_url="https://127.0.0.1:8000/healthz/ready",
        health_ca_cert="certs/adas-cert.pem",
    )

    assert result == 0
    assert calls == [
        (
            "https://127.0.0.1:8000/healthz/ready",
            {"timeout": 2, "context": context},
        )
    ]
