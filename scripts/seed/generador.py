"""Datos ficticios y coherentes entre servicios, sin tocar AWS.

Usa los constructores de claves del backend para no desincronizarse. Los ID dependen solo de la
semilla y de la fecha base: repetir la carga sobrescribe en lugar de duplicar, y por eso se puede
reanudar si la sesión de Academy termina a la mitad."""
import datetime
import importlib.util
import pathlib
import random
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "backend/common"))

from trazora_common import eventos  # noqa: E402


def _dominio(servicio, modulo):
    """Todos los servicios tienen un paquete `dominio`: se cargan por ruta para que no choquen."""
    ruta = RAIZ / "backend" / servicio / "dominio" / f"{modulo}.py"
    especificacion = importlib.util.spec_from_file_location(f"dominio_{servicio}", ruta)
    cargado = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(cargado)
    return cargado


USUARIOS = _dominio("usuarios", "usuarios")
CLIENTES = _dominio("clientes", "clientes")
TECNICOS = _dominio("tecnicos", "jornadas")
ORDENES = _dominio("ordenes", "ordenes")
AGENDA = _dominio("agenda", "agenda")
PARTES = _dominio("partes", "partes")
ANALITICA = _dominio("analitica", "analitica")

TENANTS = ("CLIMALIMA", "FRIOSUR", "TECNINORTE")
SERVICIOS = ("usuarios", "clientes", "tecnicos", "ordenes", "agenda", "partes", "analitica")
BASE_POR_TENANT = {"usuarios": 10000, "clientes": 10000, "tecnicos": 50, "ordenes": 10000, "programadas": 20}
DIAS_BASE = 200
PROPORCION_REVISITA = 0.06
INTERVALOS = [{"inicio": "08:00", "fin": "12:00"}, {"inicio": "13:00", "fin": "17:00"}]
HORAS_VISITA = ("08:00", "10:00", "13:00", "15:00")  # Separadas 2 h: la visita más larga dura 2 h.
DURACIONES = (30, 60, 90, 120)
TIPOS = sorted(ORDENES.TIPOS_SERVICIO)
COMBINACIONES = [TIPOS[:2], TIPOS[1:], [TIPOS[0], TIPOS[2]], TIPOS]
NOMBRES = ("Ana", "Carlos", "Lucía", "Jorge", "María", "Luis", "Rosa", "Pedro", "Elena", "Diego", "Carmen", "Raúl", "Sofía", "Miguel")
APELLIDOS = ("Quispe", "Flores", "Sánchez", "Rojas", "Díaz", "Torres", "Vargas", "Castillo", "Mendoza", "Ramos", "Huamán", "Paredes")
COMERCIOS = ("Comercial", "Inversiones", "Restaurante", "Clínica", "Hotel", "Bodega", "Oficinas", "Colegio", "Ferretería", "Taller")
DISTRITOS = ("Miraflores", "San Isidro", "Surco", "La Molina", "Barranco", "Lince", "Jesús María", "San Borja", "Los Olivos", "Ate")
VIAS = ("Av. Arequipa", "Av. Larco", "Jr. Unión", "Av. Benavides", "Calle Las Flores", "Av. La Marina", "Jr. Lampa", "Av. Angamos")
PROBLEMAS = ("No enfría", "Hace ruido al encender", "Gotea agua", "Instalación de equipo nuevo", "Mantenimiento semestral", "No enciende")
DIAGNOSTICOS = ("Filtro obstruido", "Falta de refrigerante", "Falla en el compresor", "Drenaje tapado", "Tarjeta electrónica dañada")
TAREAS = ("Limpieza de filtro", "Recarga de refrigerante", "Cambio de capacitor", "Prueba de funcionamiento", "Limpieza de drenaje")
MATERIALES = ("Filtro", "Refrigerante R410A", "Capacitor", "Cinta aislante")


def cantidad(clave, escala):
    return max(1, round(BASE_POR_TENANT[clave] * escala))


def _pk(tenant):
    return f"TENANT#{tenant}"


def _iso(instante):
    return AGENDA.iso(instante)


class _Empresa:
    """Genera todo lo de un tenant. La analítica se calcula después, a partir de lo generado."""

    def __init__(self, tenant, semilla, escala, base):
        self.tenant, self.base = tenant, base
        self.azar = random.Random(f"{semilla}-{tenant}")
        self.escala = escala
        self.n_tecnicos = max(5, cantidad("tecnicos", escala))
        self.dias = max(40, round(DIAS_BASE * escala))
        self.dias_pasados = self.dias * 3 // 4
        self.ocupados = set()
        self.eventos_analitica = []
        self.salida = {s: [] for s in SERVICIOS}
        self.tecnicos, self.clientes = [], []

    def _nombre_persona(self):
        return f"{self.azar.choice(NOMBRES)} {self.azar.choice(APELLIDOS)}"

    def generar(self):
        self._tecnicos()
        self._clientes()
        self._usuarios()
        for i in range(cantidad("ordenes", self.escala)):
            self._orden_cerrada(i)
        for i in range(max(5, cantidad("programadas", self.escala))):
            self._orden_programada(i)
        self._analitica()
        return self.salida

    # ---- Maestros
    def _tecnicos(self):
        pk = _pk(self.tenant)
        desde = self.base - datetime.timedelta(days=self.dias_pasados)
        for i in range(self.n_tecnicos):
            tecnico = {
                "PK": pk, "SK": TECNICOS.sk_tecnico(f"TEC-{self.tenant}-{i:04d}"), "entity_type": "TECNICO",
                "tenant_id": self.tenant, "tecnico_id": f"TEC-{self.tenant}-{i:04d}", "nombre": self._nombre_persona(),
                "especialidades": COMBINACIONES[i % len(COMBINACIONES)], "activo": True, "creado_en": _iso(self._instante(desde, "08:00")),
            }
            self.tecnicos.append(tecnico)
            self.salida["tecnicos"].append(tecnico)
            for d in range(self.dias):
                fecha = (desde + datetime.timedelta(days=d)).isoformat()
                self.salida["tecnicos"].append({
                    "PK": pk, "SK": TECNICOS.sk_jornada(tecnico["tecnico_id"], fecha), "entity_type": "JORNADA",
                    "tenant_id": self.tenant, "tecnico_id": tecnico["tecnico_id"], "fecha": fecha,
                    "zona_horaria": "America/Lima", "intervalos": INTERVALOS,
                })

    def _clientes(self):
        pk = _pk(self.tenant)
        for i in range(cantidad("clientes", self.escala)):
            cliente_id, ubicacion_id = f"CLI-{self.tenant}-{i:05d}", f"LOC-{self.tenant}-{i:05d}"
            nombre = f"{self.azar.choice(COMERCIOS)} {self.azar.choice(APELLIDOS)} {i:05d}"
            direccion = f"{self.azar.choice(VIAS)} {self.azar.randint(100, 3999)}"
            distrito = self.azar.choice(DISTRITOS)
            self.clientes.append({"cliente_id": cliente_id, "ubicacion_id": ubicacion_id, "nombre": nombre, "direccion": direccion, "distrito": distrito})
            self.salida["clientes"].append({
                "PK": pk, "SK": CLIENTES.sk_cliente(cliente_id), "entity_type": "CLIENTE", "tenant_id": self.tenant,
                "cliente_id": cliente_id, "nombre": nombre, "telefono": f"9{self.azar.randint(10000000, 99999999)}",
                "activo": True, "creado_en": f"{self.base - datetime.timedelta(days=self.dias_pasados)}T13:00:00Z",
                "GSI1PK": CLIENTES.particion_nombres(self.tenant), "GSI1SK": CLIENTES.orden_nombre(nombre, cliente_id),
            })
            self.salida["clientes"].append({
                "PK": pk, "SK": CLIENTES.sk_ubicacion(cliente_id, ubicacion_id), "entity_type": "UBICACION",
                "tenant_id": self.tenant, "cliente_id": cliente_id, "ubicacion_id": ubicacion_id,
                "nombre": "Local principal", "direccion": direccion, "distrito": distrito,
            })

    def _usuarios(self):
        """Perfiles sin contraseña ni marcador de correo: no pueden iniciar sesión."""
        for i in range(cantidad("usuarios", self.escala)):
            usuario_id = f"USR-{self.tenant}-{i:05d}"
            item = {
                "PK": _pk(self.tenant), "SK": USUARIOS.sk_usuario(usuario_id), "entity_type": "USUARIO",
                "tenant_id": self.tenant, "usuario_id": usuario_id, "email": f"perfil{i:05d}@{self.tenant.lower()}.example.com",
                "nombre": self._nombre_persona(), "rol": "COORDINADOR", "estado": USUARIOS.INACTIVO,
                "creado_en": f"{self.base - datetime.timedelta(days=self.dias_pasados)}T13:00:00Z",
            }
            if i % 2:
                item.update(rol="TECNICO", tecnico_id=self.tecnicos[i % self.n_tecnicos]["tecnico_id"])
            self.salida["usuarios"].append(item)

    # ---- Fechas
    def _instante(self, fecha, hora):
        return AGENDA.a_utc(fecha.isoformat(), hora)

    def _dia_pasado(self, minimo, maximo):
        return self.base - datetime.timedelta(days=self.azar.randint(minimo, maximo))

    def _reservar(self, tipo, fecha_minima):
        """Técnico con esa especialidad y un turno libre: nunca hay dos visitas a la vez."""
        candidatos = [t for t in self.tecnicos if tipo in t["especialidades"]]
        hoy = self.base
        while True:
            dias = max(0, (hoy - fecha_minima).days - 1)
            fecha = fecha_minima + datetime.timedelta(days=self.azar.randint(0, min(dias, 5)))
            tecnico, hora = self.azar.choice(candidatos), self.azar.choice(HORAS_VISITA)
            clave = (tecnico["tecnico_id"], fecha, hora)
            if clave not in self.ocupados:
                self.ocupados.add(clave)
                return tecnico, fecha, hora

    # ---- Órdenes con sus visitas y partes
    def _orden_base(self, orden_id, cliente, tipo, estado, creada, version):
        descripcion = self.azar.choice(PROBLEMAS)
        creada_txt = _iso(creada)
        return {
            "PK": _pk(self.tenant), "SK": ORDENES.sk_orden(orden_id), "entity_type": "ORDEN", "tenant_id": self.tenant,
            "orden_id": orden_id, "cliente_id": cliente["cliente_id"], "ubicacion_id": cliente["ubicacion_id"],
            "cliente_nombre": cliente["nombre"], "direccion": cliente["direccion"], "distrito": cliente["distrito"],
            "tipo_servicio": tipo, "descripcion": descripcion, "prioridad": self.azar.choice(sorted(ORDENES.PRIORIDADES)),
            "estado": estado, "version": version, "creada_en": creada_txt,
            "GSI1PK": ORDENES.particion_estado(self.tenant, estado), "GSI1SK": f"{creada_txt}#{orden_id}",
            "GSI2PK": ORDENES.particion_cliente(self.tenant, cliente["cliente_id"]), "GSI2SK": f"{creada_txt}#{orden_id}",
        }

    def _id_orden(self, creada, i):
        # Empieza por el tiempo, como en el backend: el listado queda en orden cronológico.
        return f"OT-{int(creada.timestamp() * 1000):013d}-{self.tenant[:3]}{i:05d}"

    def _historial(self, orden_id, instante, tipo, detalle, sufijo):
        texto = _iso(instante)
        return {
            "PK": _pk(self.tenant), "SK": ORDENES.sk_historial(orden_id, texto, sufijo), "entity_type": "HISTORIAL",
            "orden_id": orden_id, "tipo": tipo, "detalle": detalle, "usuario_id": "carga", "ocurrido_en": texto,
        }

    def _visita(self, orden, tecnico, fecha, hora, duracion, numero, visita_id, estado, version):
        inicio = self._instante(fecha, hora)
        fin = inicio + datetime.timedelta(minutes=duracion)
        return {
            "PK": _pk(self.tenant), "SK": AGENDA.sk_visita(visita_id), "entity_type": "VISITA", "tenant_id": self.tenant,
            "visita_id": visita_id, "orden_id": orden["orden_id"], "tecnico_id": tecnico["tecnico_id"],
            "tecnico_nombre": tecnico["nombre"], "orden_descripcion": orden["descripcion"],
            "cliente_nombre": orden["cliente_nombre"], "direccion": orden["direccion"], "distrito": orden["distrito"],
            "tipo_servicio": orden["tipo_servicio"], "inicio": _iso(inicio), "fin": _iso(fin), "fecha": AGENDA.fecha_lima(inicio),
            "estado": estado, "numero_visita_orden": numero, "version": version, "creada_en": orden["creada_en"],
            **AGENDA.claves_indices(self.tenant, tecnico["tecnico_id"], orden["orden_id"], inicio, visita_id),
        }

    def _orden_cerrada(self, i):
        cliente = self.azar.choice(self.clientes)
        tipo = self.azar.choice(TIPOS)
        creada_dia = self._dia_pasado(10, self.dias_pasados - 1)
        creada = self._instante(creada_dia, "09:00")
        orden_id = self._id_orden(creada, i)
        orden = self._orden_base(orden_id, cliente, tipo, "CERRADA", creada, 7)
        resultados = ["RESUELTO"]
        if self.azar.random() < PROPORCION_REVISITA:  # Toda orden cerrada termina con una visita resuelta.
            resultados.insert(0, self.azar.choice(["REQUIERE_REVISITA", "NO_ATENDIDO"]))

        resumen, ultima, minima = {}, None, creada_dia + datetime.timedelta(days=1)  # La atención es posterior al registro.
        for numero, resultado in enumerate(resultados, 1):
            visita_id = f"VIS-{self.tenant}-{i:05d}-{numero}"
            tecnico, fecha, hora = self._reservar(tipo, minima)
            duracion = self.azar.choice(DURACIONES)
            visita = self._visita(orden, tecnico, fecha, hora, duracion, numero, visita_id, AGENDA.FINALIZADA, 3)
            inicio = self._instante(fecha, hora)
            atencion = self.azar.randint(15, duracion)
            finalizada = inicio + datetime.timedelta(minutes=atencion)
            visita.update(resultado=resultado, iniciada_en=_iso(inicio), finalizada_en=_iso(finalizada), duracion_min=atencion)
            self.salida["agenda"].append(visita)
            self._parte(visita, resultado, finalizada, i, numero)
            resumen[visita_id] = {"estado": "FINALIZADA", "version": 3, "numero": numero, "resultado": resultado}
            self.eventos_analitica.append(("VisitaProgramada", {"tecnico_id": tecnico["tecnico_id"], "fecha": fecha.isoformat()}))
            self.eventos_analitica.append(("VisitaCompletada", {
                "tecnico_id": tecnico["tecnico_id"], "fecha": fecha.isoformat(), "resultado": resultado,
                "numero_visita_orden": numero, "duracion_min": atencion,
            }))
            ultima, minima = finalizada, fecha + datetime.timedelta(days=1)

        terminada = min(ultima + datetime.timedelta(days=self.azar.randint(0, 2)), self._instante(self.base, "08:00"))
        orden.update(resumen_visitas=resumen, terminada_en=_iso(terminada))
        self.salida["ordenes"] += [
            orden,
            self._historial(orden_id, creada, "ORDEN_CREADA", "Orden registrada", "a"),
            self._historial(orden_id, terminada, "OrdenCerrada", "Orden cerrada", "b"),
        ]
        self.eventos_analitica.append(("OrdenCreada", {"creada_en": orden["creada_en"]}))
        self.eventos_analitica.append(("OrdenCerrada", {"creada_en": orden["creada_en"], "terminada_en": _iso(terminada)}))

    def _parte(self, visita, resultado, finalizada, i, numero):
        parte_id = f"PAR-{self.tenant}-{i:05d}-{numero}"
        no_atendida = resultado == "NO_ATENDIDO"
        self.salida["partes"] += [
            {
                "PK": _pk(self.tenant), "SK": PARTES.sk_parte(parte_id), "entity_type": "PARTE", "tenant_id": self.tenant,
                "parte_id": parte_id, "visita_id": visita["visita_id"], "orden_id": visita["orden_id"], "tecnico_id": visita["tecnico_id"],
                "tecnico_nombre": visita["tecnico_nombre"], "cliente_nombre": visita["cliente_nombre"],
                "direccion": visita["direccion"], "distrito": visita["distrito"], "fecha": visita["fecha"],
                "numero_visita_orden": numero, "estado": PARTES.FINALIZADO,
                "diagnostico": "Cliente ausente" if no_atendida else self.azar.choice(DIAGNOSTICOS),
                "tareas": [] if no_atendida else self.azar.sample(TAREAS, self.azar.randint(1, 3)),
                "materiales": [] if no_atendida else self.azar.sample(MATERIALES, self.azar.randint(0, 2)),
                "resultado": resultado, "evidencias_solicitadas": 0,  # Sin referencias a archivos inexistentes.
                "version": 3, "creado_en": visita["iniciada_en"], "finalizado_en": _iso(finalizada),
                **PARTES.indice_de_orden(self.tenant, visita["orden_id"], parte_id),
            },
            {"PK": _pk(self.tenant), "SK": PARTES.sk_marca(visita["visita_id"]), "entity_type": "MARCA_VISITA", "parte_id": parte_id},
        ]

    def _orden_programada(self, i):
        """Visitas futuras para la demo: reservan sus bloques y su control, como las reales."""
        cliente = self.azar.choice(self.clientes)
        tipo = self.azar.choice(TIPOS)
        creada = self._instante(self.base - datetime.timedelta(days=1), "09:00")
        orden_id = self._id_orden(creada, 90000 + i)
        orden = self._orden_base(orden_id, cliente, tipo, "PROGRAMADA", creada, 2)
        visita_id = f"VIS-{self.tenant}-P{i:05d}"
        candidatos = [t for t in self.tecnicos if tipo in t["especialidades"]]
        while True:
            fecha = self.base + datetime.timedelta(days=self.azar.randint(1, min(20, self.dias - self.dias_pasados - 1)))
            tecnico, hora = self.azar.choice(candidatos), self.azar.choice(HORAS_VISITA)
            clave = (tecnico["tecnico_id"], fecha, hora)
            if clave not in self.ocupados:
                self.ocupados.add(clave)
                break
        visita = self._visita(orden, tecnico, fecha, hora, 60, 1, visita_id, AGENDA.PROGRAMADA, 1)
        orden["resumen_visitas"] = {visita_id: {"estado": "PROGRAMADA", "version": 1, "numero": 1}}
        self.salida["ordenes"] += [
            orden,
            self._historial(orden_id, creada, "ORDEN_CREADA", "Orden registrada", "a"),
            self._historial(orden_id, creada, "VisitaProgramada", "Visita 1 programada", "b"),
        ]
        self.salida["agenda"].append(visita)
        pk = _pk(self.tenant)
        self.salida["agenda"].append({
            "PK": pk, "SK": AGENDA.sk_control(orden_id), "entity_type": "CONTROL_ORDEN", "tenant_id": self.tenant, "orden_id": orden_id,
            "acepta_programaciones": True, "visitas_activas": 1, "visitas_total": 1,
        })
        inicio = self._instante(fecha, hora)
        for bloque in AGENDA.bloques(inicio, inicio + datetime.timedelta(minutes=60)):
            self.salida["agenda"].append({
                "PK": pk, "SK": AGENDA.sk_bloque(tecnico["tecnico_id"], bloque), "entity_type": "BLOQUE",
                "tecnico_id": tecnico["tecnico_id"], "visita_id": visita_id, "hora": AGENDA.hora_lima(bloque),
            })
        self.eventos_analitica.append(("OrdenCreada", {"creada_en": orden["creada_en"]}))
        self.eventos_analitica.append(("VisitaProgramada", {"tecnico_id": tecnico["tecnico_id"], "fecha": fecha.isoformat()}))

    # ---- Analítica
    def _analitica(self):
        """Aplica las mismas reglas que el consumidor real a lo generado: los números cuadran."""
        acumulado = {}
        for tipo, datos in self.eventos_analitica:
            evento = eventos.crear_evento(tipo, self.tenant, "CARGA", "-", 1, datos, event_id="carga")
            for sk, cambio in ANALITICA.efectos(evento).items():
                item = acumulado.setdefault(sk, dict(cambio["atributos"]))
                for nombre, valor in cambio["sumas"].items():
                    item[nombre] = item.get(nombre, 0) + valor
        desde = self.base - datetime.timedelta(days=self.dias_pasados)
        for tecnico in self.tecnicos:
            for d in range(self.dias):  # Un registro por técnico y día, también en los días sin visitas.
                fecha = (desde + datetime.timedelta(days=d)).isoformat()
                acumulado.setdefault(ANALITICA.sk_dia(fecha, tecnico["tecnico_id"]), {
                    "entity_type": "SNAPSHOT_TECNICO_DIA", "tecnico_id": tecnico["tecnico_id"], "fecha": fecha, "visitas_asignadas": 0,
                })
        ahora = f"{self.base}T13:00:00Z"
        self.salida["analitica"] = [
            {"PK": _pk(self.tenant), "SK": sk, "tenant_id": self.tenant, "ultima_actualizacion": ahora, **item}
            for sk, item in acumulado.items()
        ]


def generar_tenant(tenant, semilla=2032, escala=1.0, base=None):
    """{servicio: [ítems]} de un tenant."""
    base = base or datetime.date.today()
    return _Empresa(tenant, semilla, escala, base).generar()
