'use strict';

// Las declaraciones http de Serverless son el contrato que usan también OpenAPI y el frontend.
const { createHash } = require('node:crypto');
const servicios = ['usuarios', 'clientes', 'tecnicos', 'ordenes', 'agenda', 'partes', 'analitica'];
const parametro = /^\{([a-zA-Z0-9_]+)\}$/;
const ref = (id) => ({ Ref: id });
const contexto = (why, must) => ({ 'com.aws.cloudformation.Context': { why, must } });

function rutas(servicio) {
  return Object.entries(servicio.functions).flatMap(([funcion, spec]) =>
    (spec.events || []).filter((evento) => evento.http).map(({ http }) => ({
      funcion, spec, ruta: http.path, metodo: http.method.toUpperCase(), protegida: Boolean(http.authorizer),
    }))
  );
}

function compilarRuta(recursos, naming, red, stage, servicio, entrada, prioridades) {
  const { funcion, ruta, metodo, protegida } = entrada;
  const metodoId = naming.getMethodLogicalId(naming.normalizePath(ruta), metodo);
  const lambdaId = naming.getLambdaLogicalId(funcion);
  const permisoApi = naming.getLambdaApiGatewayPermissionLogicalId(funcion);
  const method = recursos[metodoId];
  if (method?.Properties.Integration.Type !== 'AWS_PROXY' || !method.DependsOn.includes(permisoApi)) {
    throw new Error('No se encontró el método Lambda compilado para ' + metodo + ' /' + ruta);
  }
  if (!protegida && !(metodo === 'POST' && ruta === 'auth/login')) {
    throw new Error('Falta el autorizador para ' + metodo + ' /' + ruta);
  }

  const parametros = { 'integration.request.header.X-Trazora-Request-Id': 'context.requestId' };
  if (protegida) {
    parametros['integration.request.header.X-Trazora-Identity'] = 'context.authorizer.identidadAlb';
  }
  const segmentos = ruta.split('/');
  let variables = 0;
  const patron = segmentos.map((segmento) => {
    const nombre = parametro.exec(segmento)?.[1];
    if (!nombre) {
      if (!/^[a-zA-Z0-9_-]+$/.test(segmento)) throw new Error('Ruta ALB no soportada: ' + ruta);
      return segmento;
    }
    variables++;
    method.Properties.RequestParameters['method.request.path.' + nombre] = true;
    parametros['integration.request.path.' + nombre] = 'method.request.path.' + nombre;
    return '[^/]+';
  }).join('/');

  // Bloques por servicio y especificidad. Una ruta nueva no renumera las existentes.
  const hash = createHash('sha256').update(metodo + ' /' + ruta).digest();
  const prioridad = variables * 10000 + servicios.indexOf(servicio) * 1000 + hash.readUInt16BE(0) % 1000 + 1;
  if (prioridades.has(prioridad) || prioridad > 50000) throw new Error('Prioridad ALB en conflicto: ' + ruta);
  prioridades.add(prioridad);
  const grupo = lambdaId + 'TargetGroup';
  const permiso = lambdaId + 'PermisoAlb';
  const regla = metodoId + 'ReglaAlb';
  const nombreGrupo = 'trz-' + stage + '-' + servicio + '-' + hash.toString('hex').slice(0, 10);
  const arnLambda = { 'Fn::GetAtt': [lambdaId, 'Arn'] };

  recursos[permiso] = {
    Type: 'AWS::Lambda::Permission',
    Metadata: contexto('Autoriza el registro y la invocación por ELB', 'Restringir al grupo designado y a la cuenta'),
    Properties: {
      Action: 'lambda:InvokeFunction', FunctionName: arnLambda, Principal: 'elasticloadbalancing.amazonaws.com',
      SourceAccount: ref('AWS::AccountId'),
      // ELB comprueba el permiso al registrar el target. Referenciar el ARN del grupo crearía un ciclo.
      SourceArn: { 'Fn::Sub': 'arn:${AWS::Partition}:elasticloadbalancing:${AWS::Region}:${AWS::AccountId}:targetgroup/' + nombreGrupo + '/*' },
    },
  };
  recursos[grupo] = {
    Type: 'AWS::ElasticLoadBalancingV2::TargetGroup', DependsOn: permiso,
    Metadata: contexto('Entrega eventos ALB a esta operación', 'Un target Lambda y cabeceras multivalor'),
    Properties: {
      Name: nombreGrupo, TargetType: 'lambda', Targets: [{ Id: arnLambda }], HealthCheckEnabled: false,
      TargetGroupAttributes: [{ Key: 'lambda.multi_value_headers.enabled', Value: 'true' }],
    },
  };
  recursos[regla] = {
    Type: 'AWS::ElasticLoadBalancingV2::ListenerRule',
    Properties: {
      ListenerArn: red.listenerArn, Priority: prioridad,
      Conditions: [
        { Field: 'http-request-method', HttpRequestMethodConfig: { Values: [metodo] } },
        { Field: 'path-pattern', PathPatternConfig: { RegexValues: ['^/(' + stage + '/)?' + patron + '/?$'] } },
      ],
      Actions: [{ Type: 'forward', TargetGroupArn: ref(grupo) }],
    },
  };
  // REST VPC Link V2 routes by ALB ARN. The HTTP URI supplies Host and the request path.
  method.Properties.Integration = {
    Type: 'HTTP_PROXY', IntegrationHttpMethod: metodo, ConnectionType: 'VPC_LINK',
    ConnectionId: red.vpcLinkId, IntegrationTarget: red.albArn, Uri: red.albUrl + '/' + ruta,
    RequestParameters: parametros,
  };
  method.Metadata = contexto('Entrega el método REST al listener privado', 'Conservar método, ruta y autorización');
  method.DependsOn = [...method.DependsOn.filter((id) => id !== permisoApi), regla];
  delete recursos[permisoApi];
}

module.exports = class IngresoPrivado {
  constructor(serverless) {
    const { service } = serverless;
    this.hooks = {
      initialize: () => {
        const configuradas = new Set();
        for (const { funcion, spec, metodo, ruta } of rutas(service)) {
          if (configuradas.has(funcion)) throw new Error('Se esperaba una ruta por Lambda: ' + funcion);
          configuradas.add(funcion);
          spec.environment = { ...spec.environment, ALB_RUTA: metodo + ' /' + ruta };
        }
      },
      'after:package:compileEvents': () => {
        const template = service.provider.compiledCloudFormationTemplate;
        const nombre = service.provider.environment.SERVICE_NAME;
        const stage = service.provider.environment.STAGE;
        if (!servicios.includes(nombre) || !['dev', 'test', 'prod'].includes(stage)) {
          throw new Error('Servicio o ambiente desconocido para el listener');
        }
        template.Metadata = { ...template.Metadata, AWSToolsMetrics: { ...template.Metadata?.AWSToolsMetrics, AWSAgentToolkit: 'aws-cloudformation@3' } };
        template.Description = 'Microservicio ' + nombre + ' de Trazora con ingreso HTTP privado mediante VPC Link V2.';
        const prioridades = new Set();
        for (const entrada of rutas(service)) {
          compilarRuta(template.Resources, serverless.getProvider('aws').naming, service.custom.ingresoPrivado, stage, nombre, entrada, prioridades);
        }
      },
    };
  }
};
