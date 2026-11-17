"""Empaqueta el ingreso de los tres ambientes y contrasta el listener con las rutas OpenAPI."""
import argparse
import json
import re
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from zipfile import ZipFile

from validar_ambientes import ETAPAS, RAIZ, SERVICIOS, entorno_local, exigir, parametros


def copiar_fuentes(raiz):
    ignorar = shutil.ignore_patterns(".serverless", "__pycache__", "*.pyc", "tests", "trazora_common")
    shutil.copytree(RAIZ / "infra/shared", raiz / "infra/shared", ignore=ignorar)
    shutil.copy2(RAIZ / "infra/ingreso-privado.cjs", raiz / "infra")
    (raiz / "backend").mkdir()
    shutil.copy2(RAIZ / "backend/serverless.common.yml", raiz / "backend")
    for servicio in SERVICIOS:
        destino = raiz / "backend" / servicio
        shutil.copytree(RAIZ / "backend" / servicio, destino, ignore=ignorar)
        shutil.copytree(RAIZ / "backend/common/trazora_common", destino / "trazora_common",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def compilar(raiz, nombre, stage, node, cli, salida):
    carpeta = raiz / ("infra/shared" if nombre == "shared" else "backend/" + nombre)
    cmd = [node, str(cli), "package", "--stage", stage]
    cmd.extend(f"--param={k}={v}" for k, v in parametros(stage).items())
    run = subprocess.run(cmd, cwd=carpeta, env=entorno_local(), capture_output=True,
                         text=True, encoding="utf-8", errors="replace", timeout=150)
    if run.returncode:
        raise RuntimeError(f"Error de package en {stage}/{nombre}\n{run.stdout[-1800:]}\n{run.stderr[-1800:]}")
    paquete = carpeta / ".serverless"
    archivo = paquete / "cloudformation-template-update-stack.json"
    if salida:
        shutil.copy2(archivo, salida / f"{stage}-{nombre}.json")
    if nombre != "shared":
        with ZipFile(paquete / f"api-{nombre}.zip") as zipfile:
            exigir("trazora_common/alb.py" in zipfile.namelist(), "Falta el adaptador en " + nombre)
    return json.loads(archivo.read_text(encoding="utf-8"))["Resources"]


def propiedades(recursos, tipo):
    return {k: v["Properties"] for k, v in recursos.items() if v["Type"] == "AWS::" + tipo}


def verificar_red(recursos, stage):
    vpc, = propiedades(recursos, "EC2::VPC").values()
    subredes = propiedades(recursos, "EC2::Subnet")
    enlace, = propiedades(recursos, "ApiGatewayV2::VpcLink").values()
    alb, = propiedades(recursos, "ElasticLoadBalancingV2::LoadBalancer").values()
    listener, = propiedades(recursos, "ElasticLoadBalancingV2::Listener").values()
    auth, = propiedades(recursos, "ApiGateway::Authorizer").values()
    exigir(len(propiedades(recursos, "ApiGateway::RestApi")) == 1, "Gateway común")
    exigir(auth["Type"] == "REQUEST" and auth["AuthorizerResultTtlInSeconds"] == 0, "Autorización por petición")
    exigir(len(subredes) == len({s["AvailabilityZoneId"] for s in subredes.values()}) == 2, "Dos AZ")
    exigir(all(not s["MapPublicIpOnLaunch"] and s["VpcId"] == {"Ref": "VpcIngreso"} for s in subredes.values()), "Subred privada")
    exigir({s["Ref"] for s in alb["Subnets"]} == {s["Ref"] for s in enlace["SubnetIds"]} == set(subredes), "Subredes del enlace y ALB")
    exigir(enlace["Name"] == "trazora-" + stage and alb["Scheme"] == "internal" and alb["Type"] == "application", "ALB interno")
    exigir(listener["Protocol"] == "HTTP" and listener["Port"] == 80
           and "Certificates" not in listener and "SslPolicy" not in listener, "ALB privado HTTP sin ACM")
    exigir(listener["DefaultActions"][0]["FixedResponseConfig"]["StatusCode"] == "404", "Respuesta por defecto")
    grupos = propiedades(recursos, "EC2::SecurityGroup")
    sg_link, = enlace["SecurityGroupIds"]
    sg_alb, = alb["SecurityGroups"]
    ingreso, = propiedades(recursos, "EC2::SecurityGroupIngress").values()
    salida, = grupos[sg_link["Ref"]]["SecurityGroupEgress"]
    exigir(ingreso == {"GroupId": sg_alb, "SourceSecurityGroupId": sg_link, "IpProtocol": "tcp", "FromPort": 80, "ToPort": 80}, "Entrada al ALB")
    exigir(salida == {"DestinationSecurityGroupId": sg_alb, "IpProtocol": "tcp", "FromPort": 80, "ToPort": 80}, "Salida del enlace")
    exigir(grupos[sg_alb["Ref"]]["SecurityGroupEgress"] ==
           [{"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80, "CidrIp": "127.0.0.1/32"}],
           "Sin salida del ALB hacia la red")
    exigir(all(not g.get("SecurityGroupIngress") for g in grupos.values()), "Entrada extra en un grupo")
    exigir(not any(propiedades(recursos, t) for t in ("EC2::InternetGateway", "EC2::NatGateway", "EC2::Route")), "Ruta exterior")
    return vpc["CidrBlock"]


def verificar_servicio(nombre, recursos, stage):
    datos = parametros(stage)
    op = json.loads((RAIZ / f"docs/openapi/{nombre}.json").read_text(encoding="utf-8"))
    rutas = {(metodo.upper(), ruta) for ruta, ops in op["paths"].items() for metodo in ops
             if metodo in {"get", "post", "put", "patch", "delete"}}
    grupos = propiedades(recursos, "ElasticLoadBalancingV2::TargetGroup")
    reglas = propiedades(recursos, "ElasticLoadBalancingV2::ListenerRule")
    permisos = propiedades(recursos, "Lambda::Permission")
    funciones = propiedades(recursos, "Lambda::Function")
    exigir(len(grupos) == len(reglas) == len(rutas), "Targets y reglas de " + nombre)
    exigir(all("VpcConfig" not in f for f in funciones.values()), "Lambda en VPC")
    directos = [k for k, p in permisos.items() if p["Principal"] == "apigateway.amazonaws.com"]
    exigir(directos == (["PermisoAutorizador"] if nombre == "usuarios" else []), "Permiso directo " + nombre)
    verificadas, patrones = set(), []
    for mid, m in propiedades(recursos, "ApiGateway::Method").items():
        verbo, i = m["HttpMethod"], m["Integration"]
        if verbo == "OPTIONS":
            exigir(i["Type"] == "MOCK" and m["AuthorizationType"] == "NONE", "Preflight")
            continue
        ruta = i["Uri"].removeprefix(datos["albUrl"])
        clave = (verbo, ruta)
        exigir(clave in rutas and clave not in verificadas and m["RestApiId"] == datos["restApiId"], str(clave))
        exigir(i["Type"] == "HTTP_PROXY" and i["IntegrationHttpMethod"] == verbo and i["ConnectionType"] == "VPC_LINK"
               and i["IntegrationTarget"] == datos["albArn"] and i["ConnectionId"] == datos["vpcLinkId"], "Integración " + ruta)
        protegida = clave != ("POST", "/auth/login")
        exigir((m["AuthorizationType"], m.get("AuthorizerId")) ==
               (("CUSTOM", datos["authorizerId"]) if protegida else ("NONE", None)), "Autorizador " + ruta)
        cabecera = i["RequestParameters"].get("integration.request.header.X-Trazora-Identity")
        exigir(cabecera == ("context.authorizer.identidadAlb" if protegida else None), "Origen de identidad")
        for variable in re.findall(r"\{(\w+)\}", ruta):
            origen = "method.request.path." + variable
            exigir(m["RequestParameters"][origen] and i["RequestParameters"]["integration.request.path." + variable] == origen, origen)
        regla, = (reglas[k] for k in recursos[mid]["DependsOn"] if k in reglas)
        exigir(regla["ListenerArn"] == datos["listenerArn"], "Listener")
        condiciones = {cond["Field"]: cond for cond in regla["Conditions"]}
        exigir(condiciones["http-request-method"]["HttpRequestMethodConfig"]["Values"] == [verbo], "Método ALB")
        patron, = condiciones["path-pattern"]["PathPatternConfig"]["RegexValues"]
        grupo = regla["Actions"][0]["TargetGroupArn"]["Ref"]
        g = grupos[grupo]
        funcion = g["Targets"][0]["Id"]["Fn::GetAtt"][0]
        exigir(funciones[funcion]["Environment"]["Variables"]["ALB_RUTA"] == f"{verbo} {ruta}", "Target distinto")
        exigir(g["TargetType"] == "lambda" and g["TargetGroupAttributes"] ==
               [{"Key": "lambda.multi_value_headers.enabled", "Value": "true"}], "Evento ALB")
        permiso = permisos[recursos[grupo]["DependsOn"]]
        exigir(permiso["FunctionName"] == g["Targets"][0]["Id"] and permiso["SourceAccount"] == {"Ref": "AWS::AccountId"}
               and permiso["Principal"] == "elasticloadbalancing.amazonaws.com"
               and permiso["SourceArn"]["Fn::Sub"].endswith(":targetgroup/" + g["Name"] + "/*"), "Permiso ELB")
        verificadas.add(clave)
        patrones.append((regla["Priority"], verbo, re.compile(patron), ruta))
    exigir(verificadas == rutas, "Contrato " + nombre)
    return patrones


def verificar_seleccion(patrones, stage):
    exigir(len({p[0] for p in patrones}) == len(patrones) == 47, "Prioridades o rutas repetidas")
    ordenados = sorted(patrones)
    for _, verbo, _, ruta in ordenados:
        ejemplo = re.sub(r"\{\w+\}", "ID-01", ruta)
        for camino in (ejemplo, "/" + stage + ejemplo):
            elegido = next((r for _, m, patron, r in ordenados if m == verbo and patron.fullmatch(camino)), None)
            exigir(elegido == ruta, f"{verbo} {camino} llega a {elegido}")
    for camino in ("/ruta-inexistente", "/otro-stage/analitica/dashboard", "/visitas/ID/partes/sobra"):
        exigir(not any(p.fullmatch(camino) for _, _, p, _ in ordenados), "Ruta inesperada " + camino)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", type=Path, default=RAIZ / "node_modules/serverless/run.js")
    parser.add_argument("--node", default=shutil.which("node") or "node")
    parser.add_argument("--salida", type=Path, help="Guardar las plantillas compiladas para cfn-lint")
    args = parser.parse_args()
    cli = args.cli.resolve()
    if args.salida:
        args.salida.mkdir(parents=True, exist_ok=True)
    cidrs = set()
    with tempfile.TemporaryDirectory(prefix="trazora-ingreso-") as tmp:
        raiz = Path(tmp)
        copiar_fuentes(raiz)
        nombres = ("shared", *SERVICIOS)
        for stage in ETAPAS:
            with ThreadPoolExecutor(max_workers=3) as pool:
                stacks = dict(zip(nombres, pool.map(lambda n: compilar(raiz, n, stage, args.node, cli, args.salida), nombres)))
            cidrs.add(verificar_red(stacks["shared"], stage))
            patrones = [p for n in SERVICIOS for p in verificar_servicio(n, stacks[n], stage)]
            verificar_seleccion(patrones, stage)
            print(f"{stage}: 8 stacks, 2 AZ, 1 VPC Link V2, 1 ALB HTTP interno, 47 rutas y targets, 46 protegidas", flush=True)
    exigir(len(cidrs) == len(ETAPAS), "CIDR repetido entre ambientes")


if __name__ == "__main__":
    main()
