import pytest
from moto import mock_aws

from apoyo_pruebas import crear_tabla, ctx, cuerpo, entorno_aws, peticion
from trazora_common import dynamo

from dominio import jornadas as dominio
from handlers import jornadas, tecnicos
from trazora_common.http import ApiError

FECHA = "2026-11-10"
JORNADA = {"intervalos": [{"inicio": "13:00", "fin": "17:00"}, {"inicio": "08:00", "fin": "12:00"}]}


@pytest.fixture(autouse=True)
def aws(monkeypatch):
    entorno_aws(monkeypatch, "t_tecnicos")
    with mock_aws():
        dynamo.reiniciar()
        crear_tabla("t_tecnicos")
        yield
        dynamo.reiniciar()


def nuevo(nombre="Carlos", especialidades=("REPARACION",), tenant="CLIMALIMA"):
    r = tecnicos.crear(peticion(ctx(tenant), {"nombre": nombre, "especialidades": list(especialidades)}), None)
    assert r["statusCode"] == 201, r["body"]
    return cuerpo(r)


def poner_jornada(tecnico_id, fecha=FECHA, tenant="CLIMALIMA"):
    return jornadas.definir_jornada(peticion(ctx(tenant), JORNADA, {"tecnico_id": tecnico_id, "fecha": fecha}), None)


def disponibles(**query):
    return cuerpo(jornadas.disponibles(peticion(ctx(), query={"fecha": FECHA, **query}), None))["items"]


@pytest.mark.parametrize("intervalos", [
    [], "x", [{"inicio": "08:15", "fin": "12:00"}], [{"inicio": "12:00", "fin": "08:00"}],
    [{"inicio": "08:00", "fin": "12:00"}, {"inicio": "11:30", "fin": "13:00"}], [{"inicio": "25:00", "fin": "26:00"}],
])
def test_intervalos_invalidos(intervalos):
    with pytest.raises(ApiError):
        dominio.validar_intervalos(intervalos)


def test_intervalos_se_ordenan():
    assert dominio.validar_intervalos(JORNADA["intervalos"])[0]["inicio"] == "08:00"


def test_intervalos_contiguos_son_validos():
    dominio.validar_intervalos([{"inicio": "08:00", "fin": "12:00"}, {"inicio": "12:00", "fin": "13:00"}])


def test_especialidad_invalida():
    assert tecnicos.crear(peticion(ctx(), {"nombre": "A", "especialidades": ["MAGIA"]}), None)["statusCode"] == 400


def test_tecnico_no_gestiona():
    assert tecnicos.crear(peticion(ctx(rol="TECNICO"), {"nombre": "A", "especialidades": ["REPARACION"]}), None)["statusCode"] == 403
    assert tecnicos.listar(peticion(ctx(rol="TECNICO")), None)["statusCode"] == 403


def test_tecnico_solo_ve_su_propio_perfil():
    a, b = nuevo("A"), nuevo("B")
    propio = ctx(rol="TECNICO", tecnico=a["tecnico_id"])
    assert tecnicos.detalle(peticion(propio, ruta={"tecnico_id": a["tecnico_id"]}), None)["statusCode"] == 200
    assert tecnicos.detalle(peticion(propio, ruta={"tecnico_id": b["tecnico_id"]}), None)["statusCode"] == 403
    q = {"desde": FECHA, "hasta": FECHA}
    assert jornadas.consultar(peticion(propio, ruta={"tecnico_id": b["tecnico_id"]}, query=q), None)["statusCode"] == 403


def test_otra_empresa_recibe_404():
    t = nuevo()
    assert tecnicos.detalle(peticion(ctx("FRIOSUR"), ruta={"tecnico_id": t["tecnico_id"]}), None)["statusCode"] == 404
    assert poner_jornada(t["tecnico_id"], tenant="FRIOSUR")["statusCode"] == 404


def test_consulta_combina_jornadas_y_ausencias_en_el_rango():
    t = nuevo()["tecnico_id"]
    poner_jornada(t, "2026-11-10")
    poner_jornada(t, "2026-11-11")
    poner_jornada(t, "2026-11-20")
    jornadas.registrar_ausencia(peticion(ctx(), {"motivo": "Descanso"}, {"tecnico_id": t, "fecha": "2026-11-11"}), None)
    r = cuerpo(jornadas.consultar(peticion(ctx(), ruta={"tecnico_id": t}, query={"desde": "2026-11-10", "hasta": "2026-11-12"}), None))
    assert [j["fecha"] for j in r["jornadas"]] == ["2026-11-10", "2026-11-11"]
    assert [a["fecha"] for a in r["ausencias"]] == ["2026-11-11"]


def test_consulta_no_mezcla_tecnicos():
    a, b = nuevo("A")["tecnico_id"], nuevo("B")["tecnico_id"]
    poner_jornada(b)
    r = cuerpo(jornadas.consultar(peticion(ctx(), ruta={"tecnico_id": a}, query={"desde": FECHA, "hasta": FECHA}), None))
    assert r["jornadas"] == []


@pytest.mark.parametrize("q", [{"desde": "x", "hasta": FECHA}, {"desde": "2026-11-12", "hasta": "2026-11-10"}, {"desde": "2026-01-01", "hasta": "2026-12-01"}])
def test_rango_invalido(q):
    t = nuevo()["tecnico_id"]
    assert jornadas.consultar(peticion(ctx(), ruta={"tecnico_id": t}, query=q), None)["statusCode"] == 400


def test_disponibles_aplica_todos_los_filtros():
    con_jornada = nuevo("Con jornada")["tecnico_id"]
    poner_jornada(con_jornada)
    nuevo("Sin jornada")
    otra = nuevo("Otra especialidad", ("INSTALACION",))["tecnico_id"]
    poner_jornada(otra)
    ausente = nuevo("Ausente")["tecnico_id"]
    poner_jornada(ausente)
    jornadas.registrar_ausencia(peticion(ctx(), {"motivo": "x"}, {"tecnico_id": ausente, "fecha": FECHA}), None)
    inactivo = nuevo("Inactivo")["tecnico_id"]
    poner_jornada(inactivo)
    tecnicos.actualizar(peticion(ctx(), {"activo": False}, {"tecnico_id": inactivo}), None)
    ajeno = nuevo("Ajeno", tenant="FRIOSUR")["tecnico_id"]
    poner_jornada(ajeno, tenant="FRIOSUR")

    resultado = disponibles(especialidad="REPARACION")
    assert [t["nombre"] for t in resultado] == ["Con jornada"]
    assert resultado[0]["intervalos"][0] == {"inicio": "08:00", "fin": "12:00"}
    assert {t["nombre"] for t in disponibles()} == {"Con jornada", "Otra especialidad"}


def test_disponibles_valida_entrada():
    assert jornadas.disponibles(peticion(ctx(), query={"fecha": FECHA, "especialidad": "MAGIA"}), None)["statusCode"] == 400
    assert jornadas.disponibles(peticion(ctx(), query={}), None)["statusCode"] == 400
