"""Una cuenta de técnico debe apuntar a un técnico real de la misma empresa."""
import os

from trazora_common import interno, logs
from trazora_common.http import ApiError, no_encontrado


def exigir_tecnico(tenant_id, tecnico_id):
    """Lo confirma Técnicos con lambda.invoke (H1): sin ruta pública ni dependencia de despliegue."""
    try:
        existe = interno.invocar(os.environ["TECNICOS_FN"], {"tenant_id": tenant_id, "tecnico_id": tecnico_id})["existe"]
    except Exception as error:
        logs.error("tecnicos_no_disponible", tenant_id=tenant_id, tipo_error=type(error).__name__)
        raise ApiError(503, "SERVICIO_NO_DISPONIBLE", "No se pudo comprobar el técnico. Intenta de nuevo.")
    if not existe:
        raise no_encontrado("Técnico")
