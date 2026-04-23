from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture()
async def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> httpx.AsyncClient:
    db_path = tmp_path / "landed.db"
    audio_dir = tmp_path / "audio"
    monkeypatch.setenv("LANDED_DB_PATH", str(db_path))
    monkeypatch.setenv("LANDED_AUDIO_DIR", str(audio_dir))
    monkeypatch.setenv("LANDED_DISABLE_TTS", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    import database
    from main import app

    database.init_db()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client
