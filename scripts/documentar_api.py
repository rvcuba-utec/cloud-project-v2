"""Genera docs/api.md y la colección de Postman desde los serverless.yml: así no se desactualizan."""
import json
import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parents[1]
SERVICIOS = {"usuarios": "MS0 Usuarios", "clientes": "MS1 Clientes", "tecnicos": "MS2 Técnicos", "ordenes": "MS3 Órdenes",
             "agenda": "MS4 Agenda", "partes": "MS5 Partes", "analitica": "MS6 Analítica"}

rutas = {}
for s in SERVICIOS:
    funcion, lista = None, []
    for linea in (RAIZ / f"backend/{s}/serverless.yml").read_text().splitlines():
        m = re.match(r"^  (\w+):\s*(#.*)?$", linea)
        if m:
            funcion = m.group(1)
        m = re.search(r"http: \{ path: '?([^',]+)'?, method: (\w+)", linea)
        if m:
            lista.append((m.group(2).upper(), "/" + m.group(1), funcion))
    rutas[s] = lista

lineas = ["# API de Trazora FSM", "", "Generado por `scripts/documentar_api.py` desde los `serverless.yml`. La URL de cada API la imprime `./check.sh`.", "",
          "- **Autenticación:** `Authorization: Bearer <token>`, salvo `POST /auth/login`. El tenant y el rol salen del autorizador, nunca del cuerpo ni de la URL.",
          "- **Errores:** `{\"error\": {\"codigo\", \"mensaje\", \"detalle\"}}`. 400 entrada inválida, 401 sin sesión, 403 sin permiso, 404 inexistente o de otra empresa, 409 conflicto de estado, versión u horario.",
          "- **Listas:** `limit` (de 1 a 100) y `cursor`; la respuesta trae `items` y `next_cursor`.",
          "- **Creaciones repetibles:** clientes, técnicos, órdenes y visitas aceptan la cabecera `Idempotency-Key`.",
          "- **Funciones internas sin ruta** (`lambda.invoke`): `bloquearOrden` (Agenda), `disponiblesInterno` (Técnicos) y `tecnicosInterno` (Analítica).",
          "- **Colección de Postman:** `docs/postman/trazora.postman_collection.json`.", ""]
coleccion = []
for s, lista in rutas.items():
    lineas += [f"## {SERVICIOS[s]}", "", "| Método | Ruta | Función |", "|---|---|---|"] + [f"| {m} | `{r}` | `{f}` |" for m, r, f in lista] + [""]
    items = []
    for metodo, ruta, _ in lista:
        peticion = {"method": metodo, "header": [], "url": {"raw": "{{url_" + s + "}}" + re.sub(r"\{(\w+)\}", r"{{\1}}", ruta)}}
        if ruta != "/auth/login":
            peticion["header"].append({"key": "Authorization", "value": "Bearer {{token}}"})
        if metodo in ("POST", "PUT", "PATCH"):
            peticion["header"].append({"key": "Content-Type", "value": "application/json"})
            cuerpo = {"tenant_id": "CLIMALIMA", "email": "", "password": ""} if ruta == "/auth/login" else {}
            peticion["body"] = {"mode": "raw", "raw": json.dumps(cuerpo, indent=2)}
        items.append({"name": f"{metodo} {ruta}", "request": peticion})
    coleccion.append({"name": s, "item": items})
(RAIZ / "docs/api.md").write_text("\n".join(lineas), encoding="utf-8")
(RAIZ / "docs/postman/trazora.postman_collection.json").write_text(json.dumps({
    "info": {"name": "Trazora FSM", "description": "Generada desde los serverless.yml. Define url_<servicio> y token como variables.",
             "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"},
    "item": coleccion}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print({s: len(v) for s, v in rutas.items()})
