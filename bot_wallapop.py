import requests
from bs4 import BeautifulSoup
import time
import json
import os

# --- Configuración desde variables de entorno ---
TOKEN = os.environ.get("TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")

# Búsquedas separadas por coma: "mando ps4, tablet, nintendo"
BUSQUEDAS_RAW = os.environ.get("BUSQUEDA", "mando ps4, tablet, nintendo")
BUSQUEDAS = [b.strip() for b in BUSQUEDAS_RAW.split(",")]

PRECIO_MAX = int(os.environ.get("PRECIO_MAX", "200"))
SLEEP_TIME = int(os.environ.get("SLEEP_TIME", "60"))            # Intervalo búsqueda nuevos
ENVIO_PERIODICO = int(os.environ.get("ENVIO_PERIODICO", "180")) # Cada 3 minutos envía uno aunque no sea nuevo

ARCHIVO_IDS = "enviados.json"
ARCHIVO_CATALOGO = "catalogo.json"


def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "HTML"}
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"Error enviando Telegram: {e}")


def cargar_json(archivo):
    if os.path.exists(archivo):
        with open(archivo, "r") as f:
            return json.load(f)
    return {}


def guardar_json(archivo, data):
    with open(archivo, "w") as f:
        json.dump(data, f)


def buscar_productos(busqueda):
    """Busca productos y devuelve lista de (id, texto, precio, url)"""
    url = f"https://es.wallapop.com/app/search?keywords={busqueda.replace(' ', '%20')}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    productos = []
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        enlaces = soup.find_all("a", href=True)
        for enlace in enlaces:
            href = enlace["href"]
            if "/item/" in href:
                id_producto = href.split("/")[-1]
                texto = enlace.get_text(separator=" ").strip()
                if "€" in texto:
                    try:
                        precio = int(texto.split("€")[0].split()[-1].replace(".", "").replace(",", ""))
                        if precio <= PRECIO_MAX:
                            url_producto = "https://es.wallapop.com" + href
                            productos.append((id_producto, texto, precio, url_producto))
                    except:
                        continue
    except Exception as e:
        print(f"Error buscando '{busqueda}': {e}")
    return productos


def ciclo_nuevos():
    """Busca y envía solo productos nuevos no enviados antes."""
    enviados = cargar_json(ARCHIVO_IDS)
    catalogo = cargar_json(ARCHIVO_CATALOGO)

    for busqueda in BUSQUEDAS:
        print(f"🔍 Buscando nuevos: '{busqueda}'")
        productos = buscar_productos(busqueda)

        if busqueda not in catalogo:
            catalogo[busqueda] = []

        ids_catalogo = [p[0] for p in catalogo[busqueda]]

        for id_prod, texto, precio, url_prod in productos:
            # Guardar en catálogo para uso en envío periódico
            if id_prod not in ids_catalogo:
                catalogo[busqueda].append([id_prod, texto, precio, url_prod])
                ids_catalogo.append(id_prod)

            # Enviar solo si es nuevo
            if id_prod not in enviados:
                mensaje = (
                    f"🔥 <b>NUEVO CHOLLO — {busqueda.upper()}</b>\n\n"
                    f"🛒 {texto}\n"
                    f"💰 Precio: {precio}€\n\n"
                    f"🔗 {url_prod}"
                )
                enviar_telegram(mensaje)
                enviados[id_prod] = True
                print(f"✅ Nuevo enviado: {texto[:50]} - {precio}€")

    guardar_json(ARCHIVO_IDS, enviados)
    guardar_json(ARCHIVO_CATALOGO, catalogo)


# Índice para rotar qué producto toca en el envío periódico por cada búsqueda
indice_periodico = {b: 0 for b in BUSQUEDAS}


def ciclo_periodico():
    """Envía un producto de cada búsqueda aunque no sea nuevo, rotando por orden."""
    catalogo = cargar_json(ARCHIVO_CATALOGO)

    for busqueda in BUSQUEDAS:
        productos = catalogo.get(busqueda, [])
        if not productos:
            print(f"📭 Sin productos en catálogo para '{busqueda}'")
            continue

        idx = indice_periodico[busqueda] % len(productos)
        id_prod, texto, precio, url_prod = productos[idx]
        indice_periodico[busqueda] = idx + 1

        mensaje = (
            f"📦 <b>RECORDATORIO — {busqueda.upper()}</b>\n\n"
            f"🛒 {texto}\n"
            f"💰 Precio: {precio}€\n\n"
            f"🔗 {url_prod}"
        )
        enviar_telegram(mensaje)
        print(f"📤 Periódico ({busqueda}): {texto[:50]} - {precio}€")


if __name__ == "__main__":
    print(f"🤖 Bot iniciado.")
    print(f"   Búsquedas: {BUSQUEDAS}")
    print(f"   Precio máx: {PRECIO_MAX}€")
    print(f"   Intervalo nuevos: {SLEEP_TIME}s | Envío periódico: {ENVIO_PERIODICO}s")

    ultimo_periodico = time.time()

    while True:
        ciclo_nuevos()

        if time.time() - ultimo_periodico >= ENVIO_PERIODICO:
            print("📬 Ejecutando envío periódico...")
            ciclo_periodico()
            ultimo_periodico = time.time()

        print(f"⏳ Esperando {SLEEP_TIME}s...")
        time.sleep(SLEEP_TIME)