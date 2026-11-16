# Ambientes dev, test y prod

La rama define un API Gateway REST regional por ambiente. El stack `trazora-shared-<stage>` es dueño del gateway, del autorizador, del tema SNS y de los recursos de ruta `/visitas` y `/visitas/{visita_id}` que usan tanto Agenda como Partes. Cada servicio publica sus métodos en ese gateway. El login es la única ruta de negocio pública. MS0 verifica el token opaco y el estado del usuario en cada autorización. El navegador conserva las mismas 47 rutas y los mismos siete nombres de configuración.

| Recurso | dev | test | prod |
|---|---|---|---|
| API regional | trazora-dev | trazora-test | trazora-prod |
| URL de negocio | https://{id-dev}.execute-api.{región}.amazonaws.com/dev | https://{id-test}.execute-api.{región}.amazonaws.com/test | https://{id-prod}.execute-api.{región}.amazonaws.com/prod |
| Stacks | trazora-shared-dev y api-{servicio}-dev | trazora-shared-test y api-{servicio}-test | trazora-shared-prod y api-{servicio}-prod |
| 60 Lambda | api-{servicio}-dev-{función} | api-{servicio}-test-{función} | api-{servicio}-prod-{función} |
| Ocho tablas | dev-t_{entidad} | test-t_{entidad} | prod-t_{entidad} |
| Bucket privado | trazora-evidencias-dev-{cuenta} | trazora-evidencias-test-{cuenta} | trazora-evidencias-prod-{cuenta} |
| Tema SNS | dev-fsm-eventos | test-fsm-eventos | prod-fsm-eventos |
| Colas y DLQ | dev-q-{consumidor} y sufijo -dlq | test-q-{consumidor} y sufijo -dlq | prod-q-{consumidor} y sufijo -dlq |
| Pepper de MS0 | opcional, trazora/dev/usuarios/password-pepper | trazora/test/usuarios/password-pepper | trazora/prod/usuarios/password-pepper |
| Logs de Lambda | 7 días | 7 días | 14 días |
| Orígenes de carga S3 | Amplify dev y localhost:5173 | Amplify test y localhost:5173 | Origen de prod pasado por el despliegue |

Las ocho entidades son usuarios, sesiones, clientes, técnicos, órdenes, agenda, partes y analítica. En nombres de AWS se escriben sin tildes. MS0 posee las dos primeras. Los consumidores de las tres colas son Agenda, Órdenes y Analítica. Cada DLQ retiene durante 14 días. Técnicos también produce un evento de ausencia y tiene barrido de OUTBOX, además de los de Órdenes, Agenda y Partes que muestra el diagrama aportado. Las cuatro reglas ejecutan un barrido cada cinco minutos.

## Verificación local

`python scripts/validar_ambientes.py` ejecuta `serverless print` para los ocho stacks y los tres ambientes. Requiere las dependencias Node del proyecto y el acceso normal a Serverless v4. El script pasa identificadores y salidas de CloudFormation sintéticos y comprueba el gateway, las rutas, el autorizador, nombres de recursos, origen S3, secretos, retención, consumidores y ausencia de coincidencias entre ambientes. Los argumentos `--cli`, `--node` y `--salida` permiten utilizar una instalación local concreta y guardar las 24 configuraciones resueltas. Los nombres entre llaves de la tabla representan valores que asigna AWS.

## Migración desde el despliegue existente

La cuenta consultada en us-east-1 tiene siete REST API de dev. La rama cambia sus identificadores y la URL que consume Amplify. Antes de aplicar una migración, comparar el inventario con el change set del stack compartido y de cada servicio. Identificar reemplazos de métodos y gateways y comprobar que tablas, bucket, tema, colas y mappings conservan sus IDs. Una diferencia en el propietario del tema o de una cola requiere resolver la propiedad en CloudFormation antes de continuar. En el inventario consultado esos recursos de dev sí pertenecen a stacks.

Para ensayar la migración en una operación futura, usar test vacío, resolver las salidas de shared, publicar Usuarios antes de los servicios que utilizan el autorizador y actualizar los servicios en el orden de `deploy.sh`. Los despliegues de métodos de un gateway compartido deben ser secuenciales porque cada uno publica una instantánea del API. Verificar las 47 rutas y el aislamiento con dos empresas antes de cambiar la URL del frontend. En dev o prod ya existentes, conservar una copia de las URLs, de la versión de frontend y de los change sets. Si el change set elimina un gateway todavía en uso, la transición necesita una ventana acordada o una publicación en paralelo antes del corte. Revertir el cambio de frontend solo sirve mientras los endpoints anteriores sigan vivos. La nueva retención de logs también afecta a entradas históricas de mayor antigüedad.

## VPC Link y ALB del diagrama objetivo

Esta implementación conecta API Gateway REST directamente a Lambda con integración proxy. El autorizador entrega `requestContext.authorizer`, que contiene la identidad usada por los siete servicios. La variante privada dibujada requiere VPC, subredes, ALB, permisos del laboratorio y presupuesto, además de adaptar entrada, propagación verificable de identidad y respuesta del ALB. No forma parte de los recursos de la rama. CloudFormation interviene al desplegar.

[Compartir un API Gateway y recursos de rutas en Serverless](https://www.serverless.com/framework/docs/providers/aws/events/apigateway)
