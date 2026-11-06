"""Reglas que deben cumplir todos los microservicios."""
import pathlib
import re

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[2]
HANDLERS = sorted(p for p in BACKEND.glob("*/handlers/*.py"))
EXCEPCIONES_TENANT = {"usuarios/handlers/login.py"}  # El login es el único que recibe la empresa.
LEE_TENANT = re.compile(
    r"""(datos|cuerpo|body)\s*(\.get\(|\[)\s*["']tenant_id|parametro_(ruta|query)\(\s*event\s*,\s*["']tenant_id"""
)
TABLA_DE_OTRO = re.compile(r"""t_(usuarios|sesiones|clientes|tecnicos|ordenes|agenda|partes|analitica)\b""")


def _nombre(ruta):
    return ruta.relative_to(BACKEND).as_posix()


@pytest.mark.parametrize("ruta", HANDLERS, ids=_nombre)
def test_tenant_nunca_viene_del_cliente(ruta):
    if _nombre(ruta) not in EXCEPCIONES_TENANT:
        assert not LEE_TENANT.search(ruta.read_text(encoding="utf-8"))


@pytest.mark.parametrize("ruta", HANDLERS, ids=_nombre)
def test_handlers_no_nombran_tablas_directamente(ruta):
    # Las tablas llegan por variables de entorno propias del servicio.
    assert not TABLA_DE_OTRO.search(ruta.read_text(encoding="utf-8"))


@pytest.mark.parametrize("ruta", HANDLERS, ids=_nombre)
def test_nunca_se_registra_el_evento_completo(ruta):
    assert not re.search(r"print\(\s*event\s*\)", ruta.read_text(encoding="utf-8"))
