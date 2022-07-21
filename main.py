from fastapi import FastAPI
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver
from libcloud.compute.deployment import ScriptFileDeployment, ScriptDeployment
import os
from dotenv import dotenv_values
import sqlite3
from sympy import re


def id_to_cloud_name(cloud_id):
    if cloud_id == 1:
        return "GCP"
    if cloud_id == 2:
        return "AWS"
    if cloud_id == 3:
        return "Digital Ocean"


# Dotenv para guardar secrets
config = dotenv_values(".env")

# Configuración autenticación GCP
SERVICE_ACCOUNT_USERNAME = "libcloud@multicloudloadbalancer.iam.gserviceaccount.com"
SERVICE_ACCOUNT_CREDENTIALS_JSON_FILE_PATH = "./multicloudloadbalancer-4c475fb5fc9c.json"
PROJECT_ID = "multicloudloadbalancer"
PRIVATE_SSH_KEY_PATH = os.path.expanduser("~/.ssh/id_rsa_gce")

PUBLIC_IP_GCP_LOADBALANCER = "34.107.141.151:80"
PUBLIC_IP_AWS_LOADBALANCER = "caicedonia-938704499.us-east-1.elb.amazonaws.com"

# Configuración autenticación AWS
ACCESS_ID = config["ACCESS_ID"]
SECRET_KEY = config["SECRET_KEY"]

# Driver GCP
ComputeEngine = get_driver(Provider.GCE)
driver = ComputeEngine(
    SERVICE_ACCOUNT_USERNAME,
    SERVICE_ACCOUNT_CREDENTIALS_JSON_FILE_PATH,
    project=PROJECT_ID,
    datacenter="us-central1-c",
)

# DB
# conn = sqlite3.connect('caicedonia.db')
# conn.execute('''CREATE TABLE cloud_providers
#         (id INT PRIMARY KEY NOT NULL,
#         count INT NOT NULL,
#         link CHAR(256));''')

# GCP
# conn.execute("INSERT INTO cloud_providers (id, count, link) \
#      VALUES (1, 2, 'http://34.107.141.151:80')");

# AWS
# conn.execute("INSERT INTO cloud_providers (id, count, link) \
#      VALUES (2, 2, 'http://caicedonia-938704499.us-east-1.elb.amazonaws.com')");

# digital ocean
# conn.execute("INSERT INTO cloud_providers (id, count, link) \
#      VALUES (3, 'Paul', 32, 'California', 20000.00 )");
# conn.commit()


# Driver AWS
cls = get_driver(Provider.EC2)
driver_aws = cls(ACCESS_ID, SECRET_KEY, region="us-east-1")

# API
app = FastAPI(title='Poke distribuido', description='pokemones distribuidos', version='1.0.0')


class NameNumberVMS:
    def __init__(self, name, n_vms):
        self.name = name
        self.n_vms = n_vms


@app.get('/')
async def index(pokemon_name: str = "ditto"):
    import requests
    import json

    # Nodos de los servicios
    nodes = driver.list_nodes()
    nodes_aws = driver_aws.list_nodes()

    # Reiniciar nodos fuera de servicio
    filter_nodes_restart = [x for x in nodes if x.state.value == "stopped" and "pokeapi" in x.name]
    for node in filter_nodes_restart:
        driver.start_node(node)

    filter_nodes_restart = [x for x in nodes_aws if x.state.value == "stopped" and "pokeapi" in x.name]
    for node in filter_nodes_restart:
        driver_aws.start_node(node)

    # Nodos filtrados por los que estén activos y running (con ip pública activa)
    filter_nodes_gcp = [x for x in nodes if x.state.value == "running" and "pokeapi" in x.name]
    filter_nodes_aws = [x for x in nodes_aws if x.state.value == "running" and "pokeapi" in x.name]

    # Lista donde se juntan todos los servicios e ips
    list_of_public_ips = []

    # Servicios GCP
    for i in range(0, len(filter_nodes_gcp)):
        list_of_public_ips.append(("GCP", filter_nodes_gcp[i].public_ips[0]))

    # Servicios AWS
    for i in range(0, len(filter_nodes_aws)):
        list_of_public_ips.append(("AWS", filter_nodes_aws[i].public_ips[0]))

    cloud_url = ""
    nube_origen = ""
    reset = True

    conn = sqlite3.connect('caicedonia.db')

    cursor = conn.execute("SELECT id, count, link from cloud_providers")
    i = 1
    for row in cursor:
        dummy = False
        if row[1] > len(filter_nodes_gcp) and row[0] == 1:
            conn.execute(f"UPDATE cloud_providers set count = {len(filter_nodes_gcp)} where id = {i}")
            dummy = True

        if row[1] > len(filter_nodes_aws) and row[0] == 2:
            conn.execute(f"UPDATE cloud_providers set count = {len(filter_nodes_aws)} where id = {i}")
            dummy = True

        if dummy:
            if row[0] == 1:
                if len(filter_nodes_gcp) > 0:
                    conn.execute(f"UPDATE cloud_providers set count = {(len(filter_nodes_gcp) - 1)} where id = {i}")
                    nube_origen = id_to_cloud_name(row[0])
                    cloud_url = row[2]
                    reset = False
                    break
            if row[0] == 2:
                if len(filter_nodes_aws) > 0:
                    conn.execute(f"UPDATE cloud_providers set count = {(len(filter_nodes_aws) - 1)} where id = {i}")
                    nube_origen = id_to_cloud_name(row[0])
                    cloud_url = row[2]
                    reset = False
                    break
        else:
            if row[1] > 0:
                conn.execute(f"UPDATE cloud_providers set count = {(row[1] - 1)} where id = {i}")
                nube_origen = id_to_cloud_name(row[0])
                cloud_url = row[2]
                reset = False
                break
        i += 1

    if reset:
        conn.execute(f"UPDATE cloud_providers set count = {(len(filter_nodes_gcp) - 1)} where id = 1")
        conn.execute(f"UPDATE cloud_providers set count = {len(filter_nodes_aws)} where id = 2")
        # conn.execute(f"UPDATE cloud_providers set count = {len(filter_nodes_do)} where id = 3")
        cloud_url = "http://34.107.141.151:80"
        nube_origen = "GCP"

    conn.commit()
    cursor = conn.execute("SELECT id, count, link from cloud_providers")
    # for row in cursor:
    #    print("ID = ", row[0])
    #    print("count = ", row[1])
    #    print("url = ", row[2], "\n")
    conn.close()

    # Lógica balanceador
    # for i in range(0, len(list_of_public_ips)):
    r = requests.get(cloud_url + "/api/v2/pokemon/" + str(pokemon_name))
    respuesta = json.loads(r.text)

    diccionario_respuesta = {
        "status_code": r.status_code,
        "pokemon": respuesta["name"],
        "pokemon_id": respuesta["id"],
        "servicio_nube_origen": nube_origen
    }

    # Logs GCP
    if diccionario_respuesta["servicio_nube_origen"] == "GCP":
        f = open("gcp.log", "a")
        f.write(str(diccionario_respuesta))
        f.write("\n")
        f.close()

    # Logs AWS
    if diccionario_respuesta["servicio_nube_origen"] == "AWS":
        f = open("aws.log", "a")
        f.write(str(diccionario_respuesta))
        f.write("\n")
        f.close()

    print(diccionario_respuesta)
    return diccionario_respuesta
