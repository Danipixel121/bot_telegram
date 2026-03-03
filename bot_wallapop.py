import requests
from bs4 import BeautifulSoup
import time
import json
import os

# PON TU NUEVO TOKEN AQUÍ
TOKEN = "8729305812:AAH20AxLHKieabFFFFlU77bYlEmEmQdwZ5Y"
CHAT_ID = "8057839148"

BUSQUEDA = "mando ps4 original"
PRECIO_MAX = 15
ARCHIVO_IDS = "enviados.json"

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": mensaje
    }
    requests.post(url, data=data)

def cargar_ids():
    if os.path.exists(ARCHIVO_IDS):
        with open(ARCHIVO_IDS, "r") as f:
            return json.load(f)
    return []

def guardar_ids(ids):
    with open(ARCHIVO_IDS, "w") as f:
        json.dump(ids, f)

def buscar_productos():
    enviados = cargar_ids()

    url = f"https://es.wallapop.com/app/search?keywords={BUSQUEDA.replace(' ', '%20')}"
    headers = {"User-Agent": "Mozilla/5.0"}

    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, "html.parser")

    enlaces = soup.find_all("a", href=True)

    for enlace in enlaces:
        href = enlace["href"]

        if "/item/" in href:
            id_producto = href.split("/")[-1]

            if id_producto in enviados:
                continue

            texto = enlace.get_text()

            if "€" in texto:
                try:
                    precio = int(texto.split("€")[0].split()[-1])

                    if precio <= PRECIO_MAX:
                        url_producto = "https://es.wallapop.com" + href

                        mensaje = f"""🔥 POSIBLE CHOLLO

🛒 {texto}
💰 Precio: {precio}€

🔗 {url_producto}
"""
                        enviar_telegram(mensaje)

                        enviados.append(id_producto)
                        guardar_ids(enviados)

                except:
                    pass

while True:
    print("Buscando chollos...")
    buscar_productos()
    time.sleep(600)  # 10 minutos