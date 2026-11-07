"""Coherencia de los datos generados, a escala pequeña."""
import collections
import datetime
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import generador  # noqa: E402

BASE = datetime.date(2026, 11, 10)
ESCALA = 0.02


@pytest.fixture(scope="module")
def datos():
    return generador.generar_tenant("CLIMALIMA", 2032, ESCALA, BASE)


def tipo(datos, servicio, entidad):
    return [i for i in datos[servicio] if i.get("entity_type") == entidad]


def test_es_determinista():
    a = generador.generar_tenant("FRIOSUR", 7, 0.005, BASE)
    b = generador.generar_tenant("FRIOSUR", 7, 0.005, BASE)
    assert a == b


def test_tenants_no_comparten_ids():
    a = generador.generar_tenant("FRIOSUR", 7, 0.005, BASE)
    b = generador.generar_tenant("TECNINORTE", 7, 0.005, BASE)
    assert not {i["cliente_id"] for i in tipo(a, "clientes", "CLIENTE")} & {i["cliente_id"] for i in tipo(b, "clientes", "CLIENTE")}


def test_claves_unicas_en_cada_servicio(datos):
    for servicio, items in datos.items():
        claves = [(i["PK"], i["SK"]) for i in items]
        assert len(claves) == len(set(claves)), servicio


def test_todo_pertenece_al_tenant(datos):
    for items in datos.values():
        assert {i["PK"] for i in items} == {"TENANT#CLIMALIMA"}


def test_perfiles_cargados_no_pueden_iniciar_sesion(datos):
    usuarios = tipo(datos, "usuarios", "USUARIO")
    assert usuarios and all(u["estado"] == "INACTIVO" and "password_hash" not in u for u in usuarios)
    assert not tipo(datos, "usuarios", "EMAIL")


def test_ordenes_cerradas_terminan_resueltas_y_coinciden_con_sus_visitas(datos):
    visitas = {v["visita_id"]: v for v in tipo(datos, "agenda", "VISITA")}
    cerradas = [o for o in tipo(datos, "ordenes", "ORDEN") if o["estado"] == "CERRADA"]
    assert cerradas
    for orden in cerradas:
        resumen = orden["resumen_visitas"]
        ultima = max(resumen.values(), key=lambda v: v["numero"])
        assert ultima["resultado"] == "RESUELTO"
        assert orden["GSI1PK"] == "TENANT#CLIMALIMA#ESTADO#CERRADA"
        assert orden["terminada_en"] >= orden["creada_en"]
        for visita_id in resumen:
            v = visitas[visita_id]
            assert v["orden_id"] == orden["orden_id"] and v["cliente_nombre"] == orden["cliente_nombre"]


def test_hay_revisitas(datos):
    resultados = collections.Counter(v["resultado"] for v in tipo(datos, "agenda", "VISITA") if "resultado" in v)
    assert resultados["RESUELTO"] and (resultados["REQUIERE_REVISITA"] + resultados["NO_ATENDIDO"])


def test_visitas_dentro_de_jornada_con_tecnico_compatible_y_sin_solaparse(datos):
    tecnicos = {t["tecnico_id"]: t for t in tipo(datos, "tecnicos", "TECNICO")}
    jornadas = {(j["tecnico_id"], j["fecha"]) for j in tipo(datos, "tecnicos", "JORNADA")}
    ocupado = set()
    for v in tipo(datos, "agenda", "VISITA"):
        assert v["tipo_servicio"] in tecnicos[v["tecnico_id"]]["especialidades"]
        assert v["tecnico_nombre"] == tecnicos[v["tecnico_id"]]["nombre"]
        assert (v["tecnico_id"], v["fecha"]) in jornadas
        inicio = generador.AGENDA.leer_instante(v["inicio"], "inicio")
        fin = generador.AGENDA.leer_instante(v["fin"], "fin")
        assert generador.AGENDA.dentro_de_jornada(generador.INTERVALOS, inicio, fin)
        for b in generador.AGENDA.bloques(inicio, fin):
            clave = (v["tecnico_id"], b)
            assert clave not in ocupado
            ocupado.add(clave)


def test_cada_parte_finalizado_tiene_su_visita_y_marca(datos):
    visitas = {v["visita_id"]: v for v in tipo(datos, "agenda", "VISITA")}
    marcas = {m["SK"]: m["parte_id"] for m in tipo(datos, "partes", "MARCA_VISITA")}
    for p in tipo(datos, "partes", "PARTE"):
        v = visitas[p["visita_id"]]
        assert v["estado"] == "FINALIZADA" and v["resultado"] == p["resultado"] and v["tecnico_id"] == p["tecnico_id"]
        assert marcas[f"MARCA_VISITA#{p['visita_id']}"] == p["parte_id"]
        assert p["evidencias_solicitadas"] == 0


def test_programadas_tienen_bloques_y_control_coherentes(datos):
    programadas = [v for v in tipo(datos, "agenda", "VISITA") if v["estado"] == "PROGRAMADA"]
    assert programadas
    controles = {c["orden_id"]: c for c in tipo(datos, "agenda", "CONTROL_ORDEN")}
    bloques = collections.Counter(b["visita_id"] for b in tipo(datos, "agenda", "BLOQUE"))
    for v in programadas:
        assert v["fecha"] > BASE.isoformat()
        assert controles[v["orden_id"]]["visitas_activas"] == 1
        assert bloques[v["visita_id"]] == 2


def test_analitica_cuadra_con_lo_generado(datos):
    finalizadas = [v for v in tipo(datos, "agenda", "VISITA") if v["estado"] == "FINALIZADA"]
    metricas = tipo(datos, "analitica", "METRICAS_TECNICO")
    assert sum(m["visitas_completadas_total"] for m in metricas) == len(finalizadas)
    assert sum(m["suma_minutos"] for m in metricas) == sum(v["duracion_min"] for v in finalizadas)
    primeras = [v for v in finalizadas if v["numero_visita_orden"] == 1]
    assert sum(m["primer_intento_total"] for m in metricas) == len(primeras)
    assert sum(m["primer_intento_resueltos"] for m in metricas) == sum(v["resultado"] == "RESUELTO" for v in primeras)

    meses = tipo(datos, "analitica", "SNAPSHOT_TENANT")
    ordenes = tipo(datos, "ordenes", "ORDEN")
    assert sum(m.get("ordenes_creadas", 0) for m in meses) == len(ordenes)
    assert sum(m.get("ordenes_cerradas", 0) for m in meses) == sum(o["estado"] == "CERRADA" for o in ordenes)
    assert sum(m.get("ordenes_abiertas", 0) for m in meses) == sum(o["estado"] != "CERRADA" for o in ordenes)


def test_volumen_completo_supera_el_minimo_sin_generar():
    """A escala 1 cada servicio llega al mínimo de 10 000 por tenant, sin contar ítems técnicos."""
    assert generador.cantidad("usuarios", 1) == 10000
    assert generador.cantidad("clientes", 1) == 10000
    assert generador.cantidad("ordenes", 1) == 10000
    assert generador.cantidad("tecnicos", 1) * generador.DIAS_BASE == 10000
