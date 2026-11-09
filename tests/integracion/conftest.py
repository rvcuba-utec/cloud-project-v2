import os
import pathlib

import pytest

from apoyo import http, url_servicio

RAIZ = pathlib.Path(__file__).resolve().parents[2]
STAGE = os.environ.get("STAGE", "dev")


@pytest.fixture(scope="session")
def api_usuarios():
    return url_servicio("usuarios")


@pytest.fixture(scope="session")
def cuentas():
    filas = (RAIZ / ".demo-credentials").read_text(encoding="utf-8").splitlines()
    datos = [f.split() for f in filas if f and not f.startswith("#")]
    return {(f[1], f[4]): {"tenant_id": f[1], "email": f[2], "password": f[3]} for f in datos if f[0] == STAGE}


@pytest.fixture(scope="session")
def token_de(api_usuarios, cuentas):
    guardados = {}

    def obtener(tenant, rol="ADMIN"):
        if (tenant, rol) not in guardados:
            estado, _, datos = http(f"{api_usuarios}/auth/login", "POST", cuerpo=cuentas[(tenant, rol)])
            assert estado == 200, datos
            guardados[(tenant, rol)] = datos["token"]
        return guardados[(tenant, rol)]

    return obtener
