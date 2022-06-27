from fastapi import FastAPI 


app = FastAPI(title='Poke distribuido', description='pokemones distribuidos', version='1.0.0')


@app.get('/')
async def index():
    import requests
    import json

    r = requests.get("https://pokeapi.co/api/v2/pokemon/ditto")
    respuesta = json.loads(r.text)

    diccionario_respuesta = {
        "status_code": r.status_code,
        "pokemon": respuesta["name"],
        "respuesta": respuesta
    }
    return diccionario_respuesta
