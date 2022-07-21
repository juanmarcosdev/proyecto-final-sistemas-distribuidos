"""Main para el proyecto de sistemas distribuidos"""
import os
import sqlite3
import requests
import json
import threading
from sympy import re

from dotenv import dotenv_values
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver

from fastapi import FastAPI

# Dotenv para guardar secrets
CONFIG = dotenv_values(".env")

# Configuración autenticación GCP
SERVICE_ACCOUNT_USERNAME = "libcloud@multicloudloadbalancer.iam.gserviceaccount.com"
SERVICE_ACCOUNT_CREDENTIALS_JSON_FILE_PATH = "./multicloudloadbalancer-4c475fb5fc9c.json"
PROJECT_ID = "multicloudloadbalancer"
PRIVATE_SSH_KEY_PATH = os.path.expanduser("~/.ssh/id_rsa_gce")

# IP's de los balanceadores de carga a los cuales dirigir las peticiones
PUBLIC_IP_GCP_LOADBALANCER = "34.107.141.151:80"
PUBLIC_IP_AWS_LOADBALANCER = "caicedonia-938704499.us-east-1.elb.amazonaws.com"

# Configuración autenticación AWS
ACCESS_ID = CONFIG["ACCESS_ID"]
SECRET_KEY = CONFIG["SECRET_KEY"]

# Driver GCP
ComputeEngine = get_driver(Provider.GCE)
driver = ComputeEngine(
    SERVICE_ACCOUNT_USERNAME,
    SERVICE_ACCOUNT_CREDENTIALS_JSON_FILE_PATH,
    project=PROJECT_ID,
    datacenter="us-central1-c",
)

# Driver AWS
cls = get_driver(Provider.EC2)
driver_aws = cls(ACCESS_ID, SECRET_KEY, region="us-east-1")

# Defiinición de APP
app = FastAPI(title='Poke distribuido', description='pokemones distribuidos', version='1.0.0')


class NameNumberVMS:
    def __init__(self, name, n_vms):
        self.name = name
        self.n_vms = n_vms


def id_to_cloud_name(cloud_id) -> str:
    """Mapeo de servicios disponibles"""

    if cloud_id == 1:
        return "GCP"
    if cloud_id == 2:
        return "AWS"
    if cloud_id == 3:
        return "Digital Ocean"


def iniciar_nodos_parados(nodos_reiniciar: list, driver_usar):
    """Función para iniciar todos los nodos en la lista de nodos_reiniciar haciendo
    uso del driver en el parametro"""

    for node in nodos_reiniciar:
        driver_usar.start_node(node)


def lista_nodos_estado(lista_nodos: list, estado: str) -> list:
    """Función que retorna la lista de nodos que cumplan con la condición de estado"""

    respuesta = [x for x in lista_nodos if x.state.value == estado and "pokeapi" in x.name]
    return respuesta

def heuristic_load_balancer(filter_nodes_gcp: list, filter_nodes_aws: list):
    """Función que determina cual va a ser el proveedor de la nube a recibir la petición"""

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
    #cursor = conn.execute("SELECT id, count, link from cloud_providers")
    #for row in cursor:
    #    print("ID = ", row[0])
    #    print("count = ", row[1])
    #    print("url = ", row[2], "\n")
    conn.close()

    return cloud_url, nube_origen


def write_log(diccionario_respuesta: dict, mensaje_especial):
    """Función para escribir en el log correspondiente"""
    try:
        # Logs GCP
        if diccionario_respuesta["servicio_nube_origen"] == "GCP":
            f = open("gcp.log", "a")
            f.write(str(diccionario_respuesta))
            f.write("\n")
            f.close()
        # Logs AWS
        elif diccionario_respuesta["servicio_nube_origen"] == "AWS":
            f = open("aws.log", "a")
            f.write(str(diccionario_respuesta))
            f.write("\n")
            f.close()
        else:
            f = open("error.log", "a")
            f.write(str(mensaje_especial))
            f.write("\n")
            f.close()
    except Exception as e:
        print("Error escribiendo logs", e)
        pass

@app.get('/')
async def index(pokemon_name: str = "ditto"):
    """Ruta principal con la que se redirige el trafico de peticiones entre servidores"""

    # Nodos de los servicios
    nodes = driver.list_nodes()
    nodes_aws = driver_aws.list_nodes()


    # Reiniciar nodos fuera de servicio
    filter_nodes_restart = lista_nodos_estado(nodes, "stopped")
    if filter_nodes_restart:
        thread_reiniciar_GCP = \
            threading.Thread(target=iniciar_nodos_parados,args=(filter_nodes_restart, driver))
        thread_reiniciar_GCP.start()

    filter_nodes_restart_AWS = lista_nodos_estado(nodes_aws, "stopped")
    if filter_nodes_restart_AWS:
        thread_reiniciar_AWS = \
            threading.Thread(target=iniciar_nodos_parados,args=(filter_nodes_restart_AWS, driver_aws))
        thread_reiniciar_AWS.start()

    # Nodos filtrados por los que estén activos y running (con ip pública activa)
    filter_nodes_gcp = lista_nodos_estado(nodes, "running")
    filter_nodes_aws = lista_nodos_estado(nodes_aws, "running")

    # Utilización de la heurística
    cloud_url, nube_origen = heuristic_load_balancer(filter_nodes_gcp, filter_nodes_aws)

    # Realización petición:
    try:
        r = requests.get(cloud_url + "/api/v2/pokemon/" + str(pokemon_name))
        respuesta = json.loads(r.text)

        if r.status_code == 200:
            diccionario_respuesta = {
                "status_code": r.status_code,
                "pokemon": respuesta["name"],
                "pokemon_id": respuesta["id"],
                "servicio_nube_origen": nube_origen
            }
        else:
            diccionario_respuesta = {
                "status_code": r.status_code,
                "servicio_nube_origen": nube_origen,
                "message": "No fue posible encontrar el pokemon.",
                "pokemon_name": pokemon_name
            }
    except Exception as e:
        diccionario_respuesta = {
            "status_code": 500,
            "servicio_nube_origen": "ERROR",
            "message": "Ocurrio un error inesperado, por favor intente más tarde."
        }
        write_log(diccionario_respuesta, e)
        return diccionario_respuesta

    write_log(diccionario_respuesta, '')
    print(diccionario_respuesta)
    return diccionario_respuesta
