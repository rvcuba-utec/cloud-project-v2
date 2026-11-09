# Guía de la demo

## Antes de empezar

1. Inicia el laboratorio de AWS Academy y pega las credenciales en `.local-env/home/.aws/credentials`.
2. Ejecuta `./check.sh --stage prod` para confirmar que todo responde.
3. Ejecuta `./warmup.sh --stage prod`. **Es obligatorio tras reiniciar el laboratorio:** Academy deshabilita los disparadores SQS al apagarse y este comando los reactiva; sin ellos, los eventos se quedan en cola. Además evita el arranque en frío.
4. La demo se hace en `prod`: https://main.d35ompbd427o7g.amplifyapp.com. Ten a mano las cuentas de `prod` en `.demo-credentials`, que está fuera de Git. Muestra el archivo solo a tu equipo.
5. Abre dos ventanas: una para el coordinador de ClimaLima y otra, de incógnito o a ancho de teléfono, para su técnico.

El código de empresa es `CLIMALIMA`, `FRIOSUR` o `TECNINORTE`.

## Recorrido

| # | Quién | Dónde | Qué mostrar |
|---|---|---|---|
| 0 | Quien exponga | `/presentacion/` | La portada pública: el tablero del encabezado muestra una reasignación en bucle |
| 1 | Coordinador | Inicio de sesión y Panel | Empresa y rol; el mapa de Lima con órdenes en rojo (sin atender), ámbar (con visita) y verde (atendidas); anillo del mes y rendimiento |
| 2 | Coordinador | Órdenes > Nueva orden | Buscar un cliente y crear la orden "El equipo no enfría", tipo Reparación |
| 3 | Coordinador | Detalle de la orden > Programar visita | "Asignar al mejor técnico" con su justificación. Para que la vea el técnico de demo, elige a Carlos Villanueva en la lista |
| 4 | Técnico | Mis visitas | Iniciar la visita desde el celular |
| 5 | Técnico | Atención | Diagnóstico, tareas y resultado. Subir una foto y verla. Probar un archivo de más de 5 MB: se rechaza |
| 6 | Técnico | Atención | Finalizar el parte: la visita cambia a Finalizada en segundos, por eventos |
| 7 | Coordinador | Detalle de la orden | La orden pasa sola a Pendiente de cierre; historial completo y parte con la foto. Cerrar la orden |
| 8 | Coordinador | Panel | Las cifras reflejan el cierre |
| 9 | Coordinador | Agenda | **El momento "wow":** en el tablero del día, "Marcar ausente" a un técnico con visitas. En segundos sus visitas pasan solas a otro técnico; aparece el aviso abajo a la derecha y, en el Panel, "Lo que el sistema resolvió solo". Si nadie está libre, la visita sale como alerta urgente con su ventana de reprogramación |
| 10 | Coordinador | Detalle de otra orden con visitas | Cancelar: el aviso dice cuántas visitas se cancelarán, y se cancelan solas |
| 11 | Coordinador de FríoSur | Órdenes y Panel | Datos y métricas de otra empresa |
| 12 | Quien exponga | Terminal o Postman | Con el token de FríoSur, pedir una orden de ClimaLima: responde 404 |
| 13 | Quien exponga | `docs/evidencias/conteos.md` | Conteos de 3 empresas y `scripts/seed/cargar_datos.py`, sin Lambda |

Si hay tiempo, finaliza un parte con **Requiere otra visita**: la orden se mantiene abierta y se puede programar otra visita.

## Si algo falla

| Síntoma | Qué hacer |
|---|---|
| La web muestra errores de red | Las credenciales no afectan a la web; revisa `./check.sh` y que el laboratorio siga activo |
| `./check.sh` dice que las credenciales caducaron | Pega las nuevas y repite |
| Una visita no cambia a Finalizada en 30 s | Usa el botón Refrescar; revisa si la cola `prod-q-agenda-dlq` tiene mensajes |
| La primera respuesta tarda varios segundos | Es un arranque en frío. Ejecuta `./warmup.sh` |
| Tarda la búsqueda de técnicos | Sin Analítica disponible, la lista sale igualmente, en orden alfabético y sin justificación |
