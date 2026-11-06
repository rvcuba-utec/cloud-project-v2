import json
import os
import pathlib
import urllib.error
import urllib.request

import boto3
import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
STAGE = os.environ.get("STAGE", "dev")


def http(url, metodo="GET", token=None, cuerpo=None, cabeceras=None):
    encabezados = {"Content-Type": "application/json", **(cabeceras or {})}
    if token:
        encabezados["Authorization"] = f"Bearer {token}"
    datos = None if cuerpo is None else json.dumps(cuerpo).encode()
    req = urllib.request.Request(url, method=metodo, headers=encabezados, data=datos)
    try:
        with urllib.request.urlopen(req, timeout=28) as r:
            estado, cab, texto = r.status, {k.lower(): v for k, v in r.headers.items()}, r.read()
    except urllib.error.HTTPError as e:
        estado, cab, texto = e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()
    try:
        return estado, cab, json.loads(texto) if texto else None
    except ValueError:
        return estado, cab, None


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
