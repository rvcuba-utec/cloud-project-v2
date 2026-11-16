# Secrets Manager en AWS Academy

MS0 puede combinar la contraseña con una clave privada adicional antes de aplicar PBKDF2 con sal. Esa clave, conocida como *pepper*, queda separada de la tabla de usuarios. Los hashes nuevos identifican la versión de la clave. Los hashes PBKDF2 anteriores siguen siendo válidos. El token de sesión conserva su formato opaco y DynamoDB almacena su hash y su expiración.

| Dato | Ubicación y uso |
|---|---|
| Pepper | Secrets Manager. Solo las funciones `crear` y `login` de Usuarios reciben el nombre. El bootstrap de cuentas también lo consulta cuando está activado. |
| Contraseñas de usuarios y tokens de sesión | Hash en DynamoDB. Los valores enviados por el usuario no van a logs ni a Secrets Manager. |
| Nombres de tablas, bucket, funciones, topic, URLs, región y stage | Configuración no sensible de Serverless y salidas del stack del mismo ambiente. |
| Credenciales temporales de Academy | Perfil local `[default]` en `.local-env/home/.aws/credentials`, excluido de Git. Las Lambda usan LabRole. |
| Clave de Serverless Framework | `config.env` local, fuera de Git. No se distribuye a las Lambda. |

El nombre es `trazora/<stage>/usuarios/password-pepper`. El secreto es JSON con dos propiedades. `activa` identifica la versión que escribe nuevos hashes y `claves` asocia cada versión admitida con al menos 32 bytes aleatorios codificados en base64. El identificador admite letras, números, guion y guion bajo. El valor administra exclusivamente la clave del servicio. Para rotarla, agregar una versión y cambiar `activa` conservando las claves de las cuentas existentes hasta regenerar sus hashes. El helper pide `AWSCURRENT`, reutiliza el cliente SDK y conserva una copia en memoria hasta cinco minutos. Una versión persistida que no figura en el caché provoca una nueva lectura.

En dev, activar con `TRAZORA_PEPPER_DEV=trazora/dev/usuarios/password-pepper` en el entorno del despliegue y del bootstrap. Test y prod exigen el secreto para crear credenciales. Ante secreto ausente, inválido, inaccesible, de otro stage o saturación, la operación que lo necesita devuelve 503 con `SECRETO_NO_DISPONIBLE`. El operador puede seguir autenticando hashes anteriores. El fallback de dev se elige explícitamente antes de activar el esquema. No se crea una clave de sustitución durante una avería.

## Permisos y lectura del laboratorio

`GetSecretValue` es la operación de runtime. Limitar a la ARN real del secreto correspondiente cuando el laboratorio permita políticas específicas. En Academy el LabRole compartido puede otorgar más acceso del que utiliza la aplicación. El código valida el nombre contra el stage y no pide secretos de otros servicios. Un secreto que use una clave KMS propia requiere también el permiso de descifrado. Conviene revisar el precio regional del secreto, sus lecturas y el presupuesto antes de crearlo.

Con las dependencias del repo y el archivo del perfil listo, en PowerShell:

```powershell
$env:AWS_SHARED_CREDENTIALS_FILE = (Resolve-Path .local-env/home/.aws/credentials).Path
$env:AWS_CONFIG_FILE = Join-Path (Get-Location) '.local-env/home/.aws/config'
$env:AWS_EC2_METADATA_DISABLED = 'true'
.venv/Scripts/python.exe scripts/preflight_academy.py --stage dev
```

El script verifica STS, consulta recursos y ejecuta `DescribeSecret`. La opción `--probar-lectura-secreto` también verifica `GetSecretValue` cuando el secreto existe y descarta el valor sin imprimirlo. La lectura de esta cuenta devolvió `ResourceNotFoundException` para los tres nombres. El permiso de creación, el uso de KMS y la lectura de un valor real quedan sin comprobar.

## MCP local en Windows

Se utilizó **AWS API MCP Server**, el servidor de AWS Labs compatible con el perfil temporal del laboratorio. En esta estación quedó instalado el paquete `awslabs.aws-api-mcp-server==1.6.0` en `.local-env/mcp-venv`. La configuración de proyecto está en `.codex/config.toml`, excluida de Git en este clon porque lleva rutas de la estación. El proceso usa stdio, perfil `default`, región `us-east-1`, `READ_OPERATIONS_ONLY=true`, telemetría desactivada y acceso de archivos por comandos bloqueado. Se verificaron el handshake, el listado de herramientas y una consulta STS de solo lectura a través de MCP con respuesta HTTP 200.

Para reproducir la instalación, ejecutar `python -m venv .local-env/mcp-venv` y `.local-env/mcp-venv/Scripts/python.exe -m pip install awslabs.aws-api-mcp-server==1.6.0`. En el proyecto de Codex, usar esta estructura y reemplazar las rutas por rutas absolutas locales.

```toml
[mcp_servers.aws-academy]
command = 'C:/ruta/proyecto/.local-env/mcp-venv/Scripts/awslabs.aws-api-mcp-server.exe'
startup_timeout_sec = 90

[mcp_servers.aws-academy.env]
AWS_SHARED_CREDENTIALS_FILE = 'C:/ruta/proyecto/.local-env/home/.aws/credentials'
AWS_CONFIG_FILE = 'C:/ruta/proyecto/.local-env/home/.aws/config'
AWS_API_MCP_PROFILE_NAME = 'default'
AWS_REGION = 'us-east-1'
READ_OPERATIONS_ONLY = 'true'
AWS_API_MCP_ALLOW_UNRESTRICTED_LOCAL_FILE_ACCESS = 'no-access'
AWS_API_MCP_TELEMETRY = 'false'
AWS_EC2_METADATA_DISABLED = 'true'
```

En una sesión nueva de Codex abierta en el clon, comprobar que aparece el servidor. El SDK del script anterior también permite hacer el inventario con el mismo perfil.

[Servidor oficial de AWS Labs](https://awslabs.github.io/mcp/servers/aws-api-mcp-server) · [Lectura de secretos en Python](https://docs.aws.amazon.com/secretsmanager/latest/userguide/retrieving-secrets-python-sdk.html)
