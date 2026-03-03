import requests
from bs4 import BeautifulSoup
import time
import json
import os

# --- Configuración desde variables de entorno ---
TOKEN = os.environ.get("TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
BUSQUEDA = os.environ.get("BUSQUEDA", "iphone")
PRECIO_MAX = int(os.environ.get("PRECIO_MAX", "200"))
SLEEP_TIME = int(os.environ.get("SLEEP_TIME", "60"))
ARCHIVO_IDS = "enviados.json"


def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "HTML"}
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"Error enviando Telegram: {e}")


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
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        enlaces = soup.find_all("a", href=True)

        encontrados = 0
        for enlace in enlaces:
            href = enlace["href"]
            if "/item/" in href:
                id_producto = href.split("/")[-1]
                if id_producto in enviados:
                    continue
                texto = enlace.get_text(separator=" ").strip()
                if "€" in texto:
                    try:
                        precio = int(texto.split("€")[0].split()[-1].replace(".", "").replace(",", ""))
                        if precio <= PRECIO_MAX:
                            url_producto = "https://es.wallapop.com" + href
                            mensaje = (
                                f"🔥 <b>POSIBLE CHOLLO</b>\n\n"
                                f"🛒 {texto}\n"
                                f"💰 Precio: {precio}€\n\n"
                                f"🔗 {url_producto}"
                            )
                            enviar_telegram(mensaje)
                            enviados.append(id_producto)
                            guardar_ids(enviados)
                            encontrados += 1
                            print(f"✅ Enviado: {texto[:50]} - {precio}€")
                    except Exception as e:
                        print(f"Error procesando producto: {e}")
                        continue

        if encontrados == 0:
            print(f"Sin nuevos chollos. Revisados {len(enlaces)} enlaces.")

    except Exception as e:
        print(f"Error en la búsqueda: {e}")


if __name__ == "__main__":
    print(f"🤖 Bot iniciado. Buscando: '{BUSQUEDA}' | Precio máx: {PRECIO_MAX}€ | Intervalo: {SLEEP_TIME}s")
    while True:
        print("🔍 Buscando chollos...")
        buscar_productos()
        print(f"⏳ Esperando {SLEEP_TIME} segundos...")
        time.sleep(SLEEP_TIME)
