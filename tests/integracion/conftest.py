import os
import pathlib

import boto3
import pytest

from apoyo import http

RAIZ = pathlib.Path(__file__).resolve().parents[2]
STAGE = os.environ.get("STAGE", "dev")


def url_servicio(servicio):
    pila = boto3.client("cloudformation").describe_stacks(StackName=f"api-{servicio}-{STAGE}")["Stacks"][0]
    return next(s["OutputValue"] for s in pila["Outputs"] if s["OutputKey"] == "ServiceEndpoint")


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
