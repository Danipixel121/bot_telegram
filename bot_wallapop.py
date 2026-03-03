import requests
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
SLEEP_TIME = int(os.environ.get("SLEEP_TIME", "60"))
ENVIO_PERIODICO = int(os.environ.get("ENVIO_PERIODICO", "180"))



ARCHIVO_IDS = "enviados.json"
ARCHIVO_CATALOGO = "catalogo.json"


def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "HTML"}
    try:
        r = requests.post(url, data=data, timeout=10)
        print(f"Telegram respuesta: {r.status_code}")
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
    """Usa la API oficial de Wallapop para buscar productos."""
    url = "https://api.wallapop.com/api/v3/general/search"
    params = {
        "keywords": busqueda,
        "max_sale_price": PRECIO_MAX,
        "order_by": "newest",
        "source": "search_box",
        "country_code": "ES",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-ES,es;q=0.9",
        "Referer": "https://es.wallapop.com/",
    }
    productos = []
    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        print(f"API Wallapop [{busqueda}]: status {r.status_code}")
        data = r.json()

        # La respuesta tiene los items en data.search_objects o data.data
        items = []
        if "search_objects" in data:
            items = data["search_objects"]
        elif "data" in data and isinstance(data["data"], list):
            items = data["data"]

        print(f"  → {len(items)} productos encontrados")

        for item in items:
            try:
                id_prod = str(item.get("id", ""))
                titulo = item.get("title", "Sin título")
                precio = float(item.get("sale_price", 0))
                moneda = item.get("currency", "EUR")
                slug = item.get("web_slug", "")
                url_prod = f"https://es.wallapop.com/item/{slug}" if slug else "https://es.wallapop.com"

                if precio <= PRECIO_MAX and id_prod:
                    productos.append((id_prod, titulo, precio, url_prod))
            except Exception as e:
                print(f"  Error procesando item: {e}")
                continue

    except Exception as e:
        print(f"Error en API Wallapop '{busqueda}': {e}")

    return productos


def ciclo_nuevos():
    enviados = cargar_json(ARCHIVO_IDS)
    catalogo = cargar_json(ARCHIVO_CATALOGO)

    for busqueda in BUSQUEDAS:
        print(f"🔍 Buscando: '{busqueda}'")
        productos = buscar_productos(busqueda)

        if busqueda not in catalogo:
            catalogo[busqueda] = []

        ids_catalogo = [p[0] for p in catalogo[busqueda]]

        for id_prod, titulo, precio, url_prod in productos:
            if id_prod not in ids_catalogo:
                catalogo[busqueda].append([id_prod, titulo, precio, url_prod])
                ids_catalogo.append(id_prod)

            if id_prod not in enviados:
                mensaje = (
                    f"🔥 <b>NUEVO CHOLLO — {busqueda.upper()}</b>\n\n"
                    f"🛒 {titulo}\n"
                    f"💰 Precio: {precio}€\n\n"
                    f"🔗 {url_prod}"
                )
                enviar_telegram(mensaje)
                enviados[id_prod] = True
                print(f"✅ Nuevo enviado: {titulo[:50]} - {precio}€")

    guardar_json(ARCHIVO_IDS, enviados)
    guardar_json(ARCHIVO_CATALOGO, catalogo)


indice_periodico = {b: 0 for b in BUSQUEDAS}


def ciclo_periodico():
    catalogo = cargar_json(ARCHIVO_CATALOGO)

    for busqueda in BUSQUEDAS:
        productos = catalogo.get(busqueda, [])
        if not productos:
            print(f"📭 Sin productos en catálogo para '{busqueda}'")
            continue

        idx = indice_periodico[busqueda] % len(productos)
        id_prod, titulo, precio, url_prod = productos[idx]
        indice_periodico[busqueda] = idx + 1

        mensaje = (
            f"📦 <b>RECORDATORIO — {busqueda.upper()}</b>\n\n"
            f"🛒 {titulo}\n"
            f"💰 Precio: {precio}€\n\n"
            f"🔗 {url_prod}"
        )
        enviar_telegram(mensaje)
        print(f"📤 Periódico ({busqueda}): {titulo[:50]} - {precio}€")


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