"""La documentación OpenAPI (docs/openapi) no puede quedar desactualizada respecto de los serverless.yml."""
import importlib.util
import json
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location("generar_openapi", RAIZ / "scripts" / "generar_openapi.py")
generador = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generador)
SERVICIOS = list(generador.SERVICIOS)


@pytest.mark.parametrize("servicio", SERVICIOS)
def test_todas_las_rutas_estan_documentadas(servicio):
    declaradas = set(generador.rutas_de_serverless(servicio))
    assert declaradas == set(generador.RUTAS[servicio]), "ejecuta scripts/generar_openapi.py y describe las rutas nuevas"


@pytest.mark.parametrize("servicio", SERVICIOS)
def test_el_archivo_publicado_coincide_con_el_generador(servicio):
    publicado = json.loads((RAIZ / "docs" / "openapi" / f"{servicio}.json").read_text(encoding="utf-8"))
    assert publicado == generador.construir(servicio), "docs/openapi está desactualizado: ejecuta scripts/generar_openapi.py"


@pytest.mark.parametrize("servicio", SERVICIOS)
def test_solo_el_login_es_publico(servicio):
    for ruta, metodos in generador.construir(servicio)["paths"].items():
        for metodo, operacion in metodos.items():
            if (servicio, ruta, metodo) != ("usuarios", "/auth/login", "post"):
                assert operacion["security"] == [{"bearerAuth": []}], f"{metodo.upper()} {ruta} debe exigir token"
