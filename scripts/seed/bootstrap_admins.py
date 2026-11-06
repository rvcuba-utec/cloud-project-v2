"""Crea empresas y cuentas iniciales, directo a DynamoDB: POST /usuarios exige un administrador,
y al inicio no existe ninguno. Se puede repetir sin duplicar. Las contraseñas se generan aquí
y solo se guardan en .demo-credentials, fuera de Git."""
import argparse
import os
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RAIZ / "backend/common"), str(RAIZ / "backend/usuarios")]

import boto3  # noqa: E402

from trazora_common import dynamo, seguridad  # noqa: E402
from dominio.usuarios import ACTIVO, SK_EMPRESA, pk, sk_email, sk_usuario  # noqa: E402

EMPRESAS = {"CLIMALIMA": "ClimaLima", "FRIOSUR": "FríoSur", "TECNINORTE": "TecniNorte"}
CUENTAS = [("admin", "ADMIN", "Administración"), ("coordinador", "COORDINADOR", "Coordinación")]
ARCHIVO = RAIZ / ".demo-credentials"


def leer_guardadas():
    if not ARCHIVO.exists():
        return []
    return [l.split() for l in ARCHIVO.read_text(encoding="utf-8").splitlines() if l and not l.startswith("#")]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True)
    stage = parser.parse_args().stage
    nombre_tabla = f"{stage}-t_usuarios"
    os.environ["TABLE_NAME"] = nombre_tabla
    tabla = boto3.resource("dynamodb").Table(nombre_tabla)
    guardadas = leer_guardadas()
    nuevas = []

    for tenant_id, nombre in EMPRESAS.items():
        tabla.put_item(Item={"PK": pk(tenant_id), "SK": SK_EMPRESA, "entity_type": "EMPRESA",
                             "tenant_id": tenant_id, "nombre": nombre})
        for prefijo, rol, nombre_cuenta in CUENTAS:
            email = f"{prefijo}@{tenant_id.lower()}.example.com"
            if tabla.get_item(Key={"PK": pk(tenant_id), "SK": sk_email(email)}).get("Item"):
                if not any(g[:3] == [stage, tenant_id, email] for g in guardadas):
                    print(f"Aviso: {email} ya existe, pero su contraseña no está en {ARCHIVO.name}")
                continue
            password = seguridad.password_aleatoria()
            usuario_id = f"USR-{tenant_id}-{prefijo.upper()}"
            dynamo.transaccion([
                {"Put": {"TableName": nombre_tabla,
                         "Item": {"PK": pk(tenant_id), "SK": sk_email(email), "entity_type": "EMAIL", "usuario_id": usuario_id},
                         "ConditionExpression": "attribute_not_exists(PK)"}},
                {"Put": {"TableName": nombre_tabla, "Item": {
                    "PK": pk(tenant_id), "SK": sk_usuario(usuario_id), "entity_type": "USUARIO",
                    "tenant_id": tenant_id, "usuario_id": usuario_id, "email": email, "nombre": f"{nombre_cuenta} {nombre}",
                    "rol": rol, "estado": ACTIVO, "password_hash": seguridad.hash_password(password),
                    "creado_en": dynamo.ahora_iso(),
                }}},
            ])
            nuevas.append([stage, tenant_id, email, password, rol])

    if nuevas:
        filas = guardadas + nuevas
        contenido = "# stage empresa correo contraseña rol\n" + "\n".join(" ".join(f) for f in filas) + "\n"
        ARCHIVO.touch(mode=0o600, exist_ok=True)
        ARCHIVO.write_text(contenido, encoding="utf-8")
        os.chmod(ARCHIVO, 0o600)
    print(f"Cuentas creadas: {len(nuevas)}. Credenciales en {ARCHIVO.name}.")


if __name__ == "__main__":
    main()
