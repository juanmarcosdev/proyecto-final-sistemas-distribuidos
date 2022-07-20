from fastapi import FastAPI 
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver
from libcloud.compute.deployment import ScriptFileDeployment, ScriptDeployment
import os
from dotenv import dotenv_values
from sympy import re 

# Dotenv para guardar secrets
config = dotenv_values(".env")

# Configuración autenticación GCP
SERVICE_ACCOUNT_USERNAME = "libcloud@multicloudloadbalancer.iam.gserviceaccount.com"
SERVICE_ACCOUNT_CREDENTIALS_JSON_FILE_PATH = "./multicloudloadbalancer-4c475fb5fc9c.json"
PROJECT_ID = "multicloudloadbalancer"
PRIVATE_SSH_KEY_PATH = os.path.expanduser("~/.ssh/id_rsa_gce")

# Configuración autenticación AWS
ACCESS_ID = config["ACCESS_ID"]
SECRET_KEY = config["SECRET_KEY"]


# Driver GCP
ComputeEngine = get_driver(Provider.GCE)
driver = ComputeEngine(
    SERVICE_ACCOUNT_USERNAME,
    SERVICE_ACCOUNT_CREDENTIALS_JSON_FILE_PATH,
    project=PROJECT_ID,
    datacenter="us-central1-a",
)

# Driver AWS
cls = get_driver(Provider.EC2)
driver_aws = cls(ACCESS_ID, SECRET_KEY, region="us-east-1")

# API
app = FastAPI(title='Poke distribuido', description='pokemones distribuidos', version='1.0.0')


@app.get('/')
async def index(pokemon_name: str = "ditto"):
    import requests
    import json

    # Nodos de los servicios
    nodes = driver.list_nodes()
    nodes_aws = driver_aws.list_nodes()

    # Nodos filtrados por los que estén activos y running (con ip pública activa)
    filter_nodes_gcp = [x for x in nodes if x.state.value == "running"]
    filter_nodes_aws = [x for x in nodes_aws if x.state.value == "running"]

    # Lista donde se juntan todos los servicios e ips
    list_of_public_ips = []

    # Servicios GCP
    for i in range(0, len(filter_nodes_gcp)):
        list_of_public_ips.append(("GCP", filter_nodes_gcp[i].public_ips[0]))

    # Servicios AWS
    for i in range(0, len(filter_nodes_aws)):
        list_of_public_ips.append(("AWS", filter_nodes_aws[i].public_ips[0]))

    # Lógica balanceador
    #for i in range(0, len(list_of_public_ips)):
    r = requests.get("http://" + list_of_public_ips[2][1] + "/api/v2/pokemon/" + str(pokemon_name))
    respuesta = json.loads(r.text)

    diccionario_respuesta = {
        "status_code": r.status_code,
        "pokemon": respuesta["name"],
        "pokemon_id": respuesta["id"],
        "servicio_nube_origen": list_of_public_ips[2][0],
        "ip_de_donde_viene": list_of_public_ips[2][1],
    }

    # Logs GCP
    if(diccionario_respuesta["servicio_nube_origen"] == "GCP"):
        f = open("gcp.log", "a")
        f.write(str(diccionario_respuesta))
        f.write("\n")
        f.close()

    # Logs AWS
    if(diccionario_respuesta["servicio_nube_origen"] == "AWS"):
        f = open("aws.log", "a")
        f.write(str(diccionario_respuesta))
        f.write("\n")
        f.close()
    
    return diccionario_respuesta
