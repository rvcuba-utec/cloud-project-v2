"""Una petición secuencial por ruta frecuente, con sesión real: un token falso solo calienta el autorizador."""
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

RAIZ = pathlib.Path(__file__).resolve().parents[1]
RUTAS = {
    "usuarios": ["/usuarios/me"],
    "clientes": ["/clientes?limit=1"],
    "tecnicos": ["/tecnicos?limit=1"],
    "ordenes": ["/ordenes?limit=1"],
    "agenda": ["/visitas?fecha=2000-01-01"],
    "partes": ["/partes?orden_id=calentamiento"],
    "analitica": ["/analitica/dashboard", "/analitica/tecnicos"],
}


def pedir(url, token=None, cuerpo=None):
    cabeceras = {"Content-Type": "application/json"}
    if token:
        cabeceras["Authorization"] = f"Bearer {token}"
    datos = json.dumps(cuerpo).encode() if cuerpo else None
    with urllib.request.urlopen(urllib.request.Request(url, data=datos, headers=cabeceras), timeout=20) as r:
        return json.loads(r.read() or "{}")


def main():
    stage = os.environ["STAGE"]
    urls = dict(a.split("=", 1) for a in sys.argv[1:])
    filas = [l.split() for l in (RAIZ / ".demo-credentials").read_text(encoding="utf-8").splitlines() if l and not l.startswith("#")]
    cuenta = next(f for f in filas if f[0] == stage and f[1] == "CLIMALIMA" and f[4] == "ADMIN")
    token = pedir(f"{urls['usuarios']}/auth/login", cuerpo={"tenant_id": cuenta[1], "email": cuenta[2], "password": cuenta[3]})["token"]
    for servicio, rutas in RUTAS.items():
        if servicio not in urls:
            continue
        for ruta in rutas:
            try:
                pedir(urls[servicio] + ruta, token)
            except urllib.error.URLError as error:
                print(f"Aviso: {servicio}{ruta}: {error}")
        print(f"Calentado: {servicio}")


if __name__ == "__main__":
    main()
