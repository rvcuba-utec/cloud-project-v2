"""Cliente HTTP mínimo para las pruebas contra AWS."""
import json
import urllib.error
import urllib.request


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
