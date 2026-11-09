"""Analítica contra AWS real: permisos y aislamiento, solo lectura."""
import pytest

from apoyo import http, url_servicio


@pytest.fixture(scope="module")
def api():
    return url_servicio("analitica")


def test_permisos_y_cors(api, token_de):
    assert http(f"{api}/analitica/dashboard")[0] == 401
    assert http(f"{api}/analitica/dashboard", token=token_de("CLIMALIMA", "TECNICO"))[0] == 403
    estado, cabeceras, datos = http(f"{api}/analitica/dashboard", token=token_de("CLIMALIMA"))
    assert estado == 200 and "periodo" in datos and "historico" in datos
    assert cabeceras["access-control-allow-origin"] == "*"


def test_una_empresa_no_ve_tecnicos_de_otra(api, token_de):
    _, _, datos = http(f"{api}/analitica/tecnicos", token=token_de("FRIOSUR"))
    assert not [m for m in datos["items"] if m["tecnico_id"].startswith("TEC-CLIMALIMA")]
