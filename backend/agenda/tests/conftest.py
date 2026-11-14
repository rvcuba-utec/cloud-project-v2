import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def ahora_fijo(monkeypatch):
    """Las pruebas usan fechas fijas: el reloj queda el 2026-11-01 a las 08:00 de Lima."""
    from datetime import datetime, timezone
    from handlers import disponibilidad, visitas
    ahora = datetime(2026, 11, 1, 13, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(disponibilidad, "ahora_utc", lambda: ahora)
    monkeypatch.setattr(visitas, "ahora_utc", lambda: ahora)
