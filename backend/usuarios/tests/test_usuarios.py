import json
import time

import boto3
import pytest
from moto import mock_aws

from trazora_common import dynamo, seguridad

from handlers import actualizar, crear, listar, login, validar_token, yo

ARN = "arn:aws:execute-api:us-east-1:123:api1/dev/GET/clientes"


def ctx(tenant="CLIMALIMA", rol="ADMIN", usuario="ADMIN-1", tecnico=""):
    return {"usuario_id": usuario, "tenant_id": tenant, "rol": rol, "tecnico_id": tecnico}


def peticion(autorizador=None, body=None, ruta=None, query=None):
    return {
        "body": json.dumps(body) if body is not None else None,
        "pathParameters": ruta,
        "queryStringParameters": query,
        "requestContext": {"authorizer": autorizador} if autorizador else {},
    }


def cuerpo(r):
    return json.loads(r["body"])


@pytest.fixture(autouse=True)
def aws(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "x")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "x")
    monkeypatch.setenv("TABLE_NAME", "t_usuarios")
    monkeypatch.setenv("TABLA_SESIONES", "t_sesiones")
    monkeypatch.setattr(seguridad, "ITERACIONES", 1000)
    monkeypatch.setattr(seguridad.hash_password, "__defaults__", (1000,))
    with mock_aws():
        dynamo.reiniciar()
        c = boto3.client("dynamodb")
        c.create_table(
            TableName="t_usuarios", BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[{"AttributeName": n, "AttributeType": "S"} for n in ("PK", "SK")],
            KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
        )
        c.create_table(
            TableName="t_sesiones", BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[{"AttributeName": "token_hash", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "token_hash", "KeyType": "HASH"}],
        )
        yield
        dynamo.reiniciar()


def crear_usuario(tenant="CLIMALIMA", email="ana@ejemplo.com", password="secreto-123", rol="COORDINADOR", **extra):
    r = crear.lambda_handler(peticion(ctx(tenant), {"email": email, "nombre": "Ana", "password": password, "rol": rol, **extra}), None)
    assert r["statusCode"] == 201, r["body"]
    return cuerpo(r)


def iniciar(tenant="CLIMALIMA", email="ana@ejemplo.com", password="secreto-123"):
    return login.lambda_handler(peticion(body={"tenant_id": tenant, "email": email, "password": password}), None)


def autorizar(token):
    return validar_token.lambda_handler({"authorizationToken": f"Bearer {token}", "methodArn": ARN}, None)


# ---- Alta
def test_alta_nunca_expone_el_hash_y_guarda_el_tenant_del_autorizador():
    r = crear.lambda_handler(peticion(ctx(), {
        "email": "Ana@Ejemplo.com ", "nombre": "Ana", "password": "secreto-123", "rol": "COORDINADOR", "tenant_id": "FRIOSUR",
    }), None)
    datos = cuerpo(r)
    assert datos["tenant_id"] == "CLIMALIMA" and datos["email"] == "ana@ejemplo.com"
    assert "password_hash" not in r["body"] and "secreto-123" not in r["body"]


@pytest.mark.parametrize("rol", ["COORDINADOR", "TECNICO"])
def test_solo_admin_crea_usuarios(rol):
    r = crear.lambda_handler(peticion(ctx(rol=rol), {"email": "a@b.co", "nombre": "A", "password": "secreto-123", "rol": "ADMIN"}), None)
    assert r["statusCode"] == 403


def test_correo_unico_por_empresa_pero_no_entre_empresas():
    crear_usuario()
    r = crear.lambda_handler(peticion(ctx(), {"email": "ana@ejemplo.com", "nombre": "A", "password": "secreto-123", "rol": "COORDINADOR"}), None)
    assert r["statusCode"] == 409 and cuerpo(r)["error"]["codigo"] == "CORREO_EN_USO"
    crear_usuario(tenant="FRIOSUR")


@pytest.mark.parametrize("campos", [
    {"email": "malo"}, {"nombre": ""}, {"password": "corta"}, {"rol": "SUPERUSUARIO"}, {"rol": "TECNICO"},
])
def test_alta_valida_entrada(campos):
    base = {"email": "a@b.co", "nombre": "A", "password": "secreto-123", "rol": "COORDINADOR"}
    assert crear.lambda_handler(peticion(ctx(), {**base, **campos}), None)["statusCode"] == 400


# ---- Login
def test_login_correcto_guarda_solo_el_hash_del_token():
    crear_usuario()
    r = iniciar()
    assert r["statusCode"] == 200
    token = cuerpo(r)["token"]
    assert "Item" not in dynamo.tabla("t_sesiones").get_item(Key={"token_hash": token})
    assert "Item" in dynamo.tabla("t_sesiones").get_item(Key={"token_hash": seguridad.hash_token(token)})


@pytest.mark.parametrize("args", [
    {"password": "incorrecta"}, {"email": "nadie@ejemplo.com"}, {"tenant": "FRIOSUR"}, {"tenant": "NOEXISTE"},
])
def test_login_rechazado_con_el_mismo_error(args):
    crear_usuario()
    r = iniciar(**args)
    assert r["statusCode"] == 401 and cuerpo(r)["error"]["codigo"] == "CREDENCIALES_INVALIDAS"


def test_perfil_sin_credenciales_no_puede_entrar():
    t = dynamo.tabla()
    t.put_item(Item={"PK": "TENANT#CLIMALIMA", "SK": "EMAIL#x@y.co", "usuario_id": "U9"})
    t.put_item(Item={"PK": "TENANT#CLIMALIMA", "SK": "USUARIO#U9", "usuario_id": "U9", "estado": "INACTIVO"})
    assert iniciar(email="x@y.co")["statusCode"] == 401


def test_cuenta_inactiva_no_inicia_sesion():
    u = crear_usuario()
    actualizar.lambda_handler(peticion(ctx(), {"estado": "INACTIVO"}, {"usuario_id": u["usuario_id"]}), None)
    assert iniciar()["statusCode"] == 401


# ---- Autorizador
def test_autorizador_entrega_contexto_y_comodin():
    crear_usuario(email="tec@e.co", rol="TECNICO", tecnico_id="TEC-1")
    resultado = autorizar(cuerpo(iniciar(email="tec@e.co"))["token"])
    c = resultado["context"]
    assert c["tenant_id"] == "CLIMALIMA" and c["rol"] == "TECNICO" and c["tecnico_id"] == "TEC-1"
    assert resultado["policyDocument"]["Statement"][0]["Resource"].endswith("api1/dev/*/*")
    assert all(isinstance(v, str) for v in c.values())


@pytest.mark.parametrize("token", ["", "no-existe"])
def test_autorizador_rechaza_tokens_invalidos(token):
    with pytest.raises(Exception, match="^Unauthorized$"):
        autorizar(token)


def test_autorizador_rechaza_sesion_vencida():
    crear_usuario()
    token = cuerpo(iniciar())["token"]
    dynamo.tabla("t_sesiones").update_item(
        Key={"token_hash": seguridad.hash_token(token)},
        UpdateExpression="SET expira_en = :v", ExpressionAttributeValues={":v": int(time.time()) - 1},
    )
    with pytest.raises(Exception, match="^Unauthorized$"):
        autorizar(token)


def test_desactivar_revoca_sesiones_existentes():
    u = crear_usuario()
    token = cuerpo(iniciar())["token"]
    autorizar(token)
    actualizar.lambda_handler(peticion(ctx(), {"estado": "INACTIVO"}, {"usuario_id": u["usuario_id"]}), None)
    with pytest.raises(Exception, match="^Unauthorized$"):
        autorizar(token)


# ---- Aislamiento
def test_listar_solo_muestra_la_empresa_del_token_aunque_pida_otra():
    crear_usuario()
    crear_usuario(tenant="FRIOSUR", email="otro@ejemplo.com")
    r = listar.lambda_handler(peticion(ctx(), query={"tenant_id": "FRIOSUR"}), None)
    datos = cuerpo(r)
    assert [i["email"] for i in datos["items"]] == ["ana@ejemplo.com"]
    assert "password_hash" not in r["body"]


def test_listar_paginado_sin_marcadores():
    for i in range(3):
        crear_usuario(email=f"u{i}@e.co")
    primera = cuerpo(listar.lambda_handler(peticion(ctx(), query={"limit": "2"}), None))
    assert len(primera["items"]) == 2 and primera["next_cursor"]
    segunda = cuerpo(listar.lambda_handler(peticion(ctx(), query={"limit": "2", "cursor": primera["next_cursor"]}), None))
    assert len(segunda["items"]) == 1 and segunda["next_cursor"] is None


def test_admin_no_modifica_usuario_de_otra_empresa():
    otro = crear_usuario(tenant="FRIOSUR")
    r = actualizar.lambda_handler(peticion(ctx(), {"rol": "ADMIN"}, {"usuario_id": otro["usuario_id"]}), None)
    assert r["statusCode"] == 404
    guardado = dynamo.tabla().get_item(Key={"PK": "TENANT#FRIOSUR", "SK": f"USUARIO#{otro['usuario_id']}"})["Item"]
    assert guardado["rol"] == "COORDINADOR"
    assert "Item" not in dynamo.tabla().get_item(Key={"PK": "TENANT#CLIMALIMA", "SK": f"USUARIO#{otro['usuario_id']}"})


def test_patch_ignora_tenant_y_hash():
    u = crear_usuario()
    r = actualizar.lambda_handler(peticion(ctx(), {"nombre": "Nueva", "tenant_id": "FRIOSUR", "password_hash": "x"}, {"usuario_id": u["usuario_id"]}), None)
    assert r["statusCode"] == 200
    item = dynamo.tabla().get_item(Key={"PK": "TENANT#CLIMALIMA", "SK": f"USUARIO#{u['usuario_id']}"})["Item"]
    assert item["tenant_id"] == "CLIMALIMA" and item["password_hash"] != "x" and item["nombre"] == "Nueva"


def test_no_puede_cambiar_su_propio_rol():
    r = actualizar.lambda_handler(peticion(ctx(usuario="ADMIN-1"), {"estado": "INACTIVO"}, {"usuario_id": "ADMIN-1"}), None)
    assert r["statusCode"] == 403


def test_pasar_a_tecnico_requiere_tecnico_id():
    u = crear_usuario()
    r = actualizar.lambda_handler(peticion(ctx(), {"rol": "TECNICO"}, {"usuario_id": u["usuario_id"]}), None)
    assert r["statusCode"] == 400


def test_coordinador_no_modifica_usuarios():
    assert actualizar.lambda_handler(peticion(ctx(rol="COORDINADOR"), {"nombre": "x"}, {"usuario_id": "U"}), None)["statusCode"] == 403


# ---- Perfil
def test_yo_devuelve_empresa_sin_datos_privados():
    u = crear_usuario()
    dynamo.tabla().put_item(Item={"PK": "TENANT#CLIMALIMA", "SK": "EMPRESA", "nombre": "ClimaLima"})
    r = yo.lambda_handler(peticion(ctx(usuario=u["usuario_id"], rol="COORDINADOR")), None)
    datos = cuerpo(r)
    assert datos["tenant_nombre"] == "ClimaLima" and datos["rol"] == "COORDINADOR"
    assert "password_hash" not in r["body"] and "PK" not in datos


def test_sin_contexto_es_401():
    assert yo.lambda_handler(peticion(), None)["statusCode"] == 401


# ---- Búsqueda y filtros
def listar_con(**query):
    return cuerpo(listar.lambda_handler(peticion(ctx(), query=query), None))


def test_busca_sin_tildes_por_nombre_o_correo_y_filtra_por_rol_y_estado():
    crear_usuario(email="maria@ejemplo.com", nombre="María Pérez", rol="COORDINADOR")
    crear_usuario(email="jose@ejemplo.com", nombre="José Ruiz", rol="ADMIN")
    assert [u["email"] for u in listar_con(q="maria")["items"]] == ["maria@ejemplo.com"]
    assert [u["email"] for u in listar_con(q="JOSE@")["items"]] == ["jose@ejemplo.com"]
    assert [u["email"] for u in listar_con(rol="ADMIN")["items"]] == ["jose@ejemplo.com"]
    assert listar_con(estado="INACTIVO")["items"] == []
    assert all("busqueda" not in u for u in listar_con()["items"])


def test_filtros_paginan_sin_perder_ni_repetir():
    for i in range(7):
        crear_usuario(email=f"c{i}@ejemplo.com", nombre=f"Coord {i}", rol="COORDINADOR")
        crear_usuario(email=f"a{i}@ejemplo.com", nombre=f"Admin {i}", rol="ADMIN")
    vistos, cursor = [], None
    while True:
        pagina = listar_con(rol="COORDINADOR", limit="3", **({"cursor": cursor} if cursor else {}))
        vistos += [u["email"] for u in pagina["items"]]
        cursor = pagina["next_cursor"]
        if not cursor:
            break
    assert sorted(vistos) == sorted(f"c{i}@ejemplo.com" for i in range(7))


@pytest.mark.parametrize("query", [{"rol": "JEFE"}, {"estado": "BORRADO"}])
def test_filtros_invalidos_son_400(query):
    assert listar.lambda_handler(peticion(ctx(), query=query), None)["statusCode"] == 400


def test_cambiar_nombre_actualiza_la_busqueda():
    u = crear_usuario(email="luis@ejemplo.com", nombre="Luis")
    actualizar.lambda_handler(peticion(ctx(), {"nombre": "Ludovico"}, {"usuario_id": u["usuario_id"]}), None)
    assert [x["email"] for x in listar_con(q="ludov")["items"]] == ["luis@ejemplo.com"]


def test_filtro_encuentra_cuentas_al_final_de_muchos_perfiles(monkeypatch):
    """Con datos de carga, los perfiles inactivos van antes que las cuentas reales en el orden de la clave."""
    monkeypatch.setattr(listar, "LECTURA_FILTRADA", 5)
    tabla = dynamo.tabla()
    for i in range(40):
        tabla.put_item(Item={"PK": "TENANT#CLIMALIMA", "SK": f"USUARIO#USR-0{i:04d}", "entity_type": "USUARIO",
                             "usuario_id": f"USR-0{i:04d}", "email": f"p{i}@x.com", "nombre": "Perfil", "rol": "COORDINADOR", "estado": "INACTIVO"})
    tabla.put_item(Item={"PK": "TENANT#CLIMALIMA", "SK": "USUARIO#USR-ADMIN", "entity_type": "USUARIO",
                         "usuario_id": "USR-ADMIN", "email": "admin@x.com", "nombre": "Admin", "rol": "ADMIN", "estado": "ACTIVO"})
    assert [u["usuario_id"] for u in listar_con(rol="ADMIN", estado="ACTIVO")["items"]] == ["USR-ADMIN"]
