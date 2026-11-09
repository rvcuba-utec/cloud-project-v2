"""Crea empresas y cuentas iniciales, directo a DynamoDB: POST /usuarios exige un administrador,
y al inicio no existe ninguno. Se puede repetir sin duplicar. Las contraseñas se generan aquí
y solo se guardan en .demo-credentials, fuera de Git."""
import argparse
import datetime
import os
import pathlib
import sys
import zoneinfo

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RAIZ / "backend/common"), str(RAIZ / "backend/usuarios")]

import boto3  # noqa: E402

from trazora_common import dynamo, seguridad  # noqa: E402
from dominio.usuarios import ACTIVO, SK_EMPRESA, pk, sk_email, sk_usuario, texto_busqueda  # noqa: E402

EMPRESAS = {"CLIMALIMA": "ClimaLima", "FRIOSUR": "FríoSur", "TECNINORTE": "TecniNorte"}
CUENTAS = [
    ("admin", "ADMIN", "Administración"),
    ("coordinador", "COORDINADOR", "Coordinación"),
    ("tecnico", "TECNICO", "Técnico de demo"),
]
# Apellidos que el generador nunca usa: en la demo no puede haber dos técnicos con el mismo nombre.
TECNICOS_DEMO = {"CLIMALIMA": "Carlos Villanueva", "FRIOSUR": "Rosa Cárdenas", "TECNINORTE": "Luis Ortega"}
ESPECIALIDADES = ["INSTALACION", "MANTENIMIENTO", "REPARACION"]
DIAS_JORNADA = 30
ARCHIVO = RAIZ / ".demo-credentials"


def leer_guardadas():
    if not ARCHIVO.exists():
        return []
    return [l.split() for l in ARCHIVO.read_text(encoding="utf-8").splitlines() if l and not l.startswith("#")]


def tecnico_demo(stage, tenant_id):
    """Perfil en MS2 con jornadas próximas, para poder programar visitas sin la carga masiva."""
    tecnico_id = f"TEC-{tenant_id}-DEMO"
    tabla = boto3.resource("dynamodb").Table(f"{stage}-t_tecnicos")
    tabla.put_item(Item={
        "PK": pk(tenant_id), "SK": f"TECNICO#{tecnico_id}", "entity_type": "TECNICO", "tenant_id": tenant_id,
        "tecnico_id": tecnico_id, "nombre": TECNICOS_DEMO[tenant_id], "especialidades": ESPECIALIDADES,
        "activo": True, "creado_en": dynamo.ahora_iso(),
    })
    hoy = datetime.datetime.now(zoneinfo.ZoneInfo("America/Lima")).date()
    with tabla.batch_writer() as lote:
        for i in range(DIAS_JORNADA):
            fecha = (hoy + datetime.timedelta(days=i)).isoformat()
            lote.put_item(Item={
                "PK": pk(tenant_id), "SK": f"JORNADA#{tecnico_id}#{fecha}", "entity_type": "JORNADA",
                "tenant_id": tenant_id, "tecnico_id": tecnico_id, "fecha": fecha, "zona_horaria": "America/Lima",
                "intervalos": [{"inicio": "08:00", "fin": "12:00"}, {"inicio": "13:00", "fin": "17:00"}],
            })
    return tecnico_id


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
        tecnico_id = tecnico_demo(stage, tenant_id)
        for prefijo, rol, nombre_cuenta in CUENTAS:
            email = f"{prefijo}@{tenant_id.lower()}.example.com"
            if tabla.get_item(Key={"PK": pk(tenant_id), "SK": sk_email(email)}).get("Item"):
                if not any(g[:3] == [stage, tenant_id, email] for g in guardadas):
                    print(f"Aviso: {email} ya existe, pero su contraseña no está en {ARCHIVO.name}")
                continue
            password = seguridad.password_aleatoria()
            usuario_id = f"USR-{tenant_id}-{prefijo.upper()}"
            extra = {"tecnico_id": tecnico_id} if rol == "TECNICO" else {}
            dynamo.transaccion([
                {"Put": {"TableName": nombre_tabla,
                         "Item": {"PK": pk(tenant_id), "SK": sk_email(email), "entity_type": "EMAIL", "usuario_id": usuario_id},
                         "ConditionExpression": "attribute_not_exists(PK)"}},
                {"Put": {"TableName": nombre_tabla, "Item": {
                    "PK": pk(tenant_id), "SK": sk_usuario(usuario_id), "entity_type": "USUARIO",
                    "tenant_id": tenant_id, "usuario_id": usuario_id, "email": email, "nombre": f"{nombre_cuenta} {nombre}",
                    "busqueda": texto_busqueda(f"{nombre_cuenta} {nombre}", email),
                    "rol": rol, "estado": ACTIVO, "password_hash": seguridad.hash_password(password),
                    "creado_en": dynamo.ahora_iso(), **extra,
                }}},
            ])
            nuevas.append([stage, tenant_id, email, password, rol])

    if nuevas:
        # Tras destruir y volver a desplegar un stage, la contraseña vieja ya no sirve: se reemplaza.
        reemplazadas = {tuple(n[:3]) for n in nuevas}
        filas = [g for g in guardadas if tuple(g[:3]) not in reemplazadas] + nuevas
        contenido = "# stage empresa correo contraseña rol\n" + "\n".join(" ".join(f) for f in filas) + "\n"
        ARCHIVO.touch(mode=0o600, exist_ok=True)
        ARCHIVO.write_text(contenido, encoding="utf-8")
        os.chmod(ARCHIVO, 0o600)
    print(f"Cuentas creadas: {len(nuevas)}. Credenciales en {ARCHIVO.name}.")


if __name__ == "__main__":
    main()
