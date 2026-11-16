"""Tiempos de espera acotados para el presupuesto de ejecución de Lambda."""
from botocore.config import Config

LECTURA = Config(connect_timeout=2, read_timeout=4, retries={"mode": "standard", "total_max_attempts": 2})
# Lambda.invoke es síncrono y puede tener efectos. Un timeout tiene resultado desconocido.
INVOCACION = Config(connect_timeout=2, read_timeout=18, retries={"mode": "standard", "total_max_attempts": 1})
