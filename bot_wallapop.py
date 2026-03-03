import requests
import time
import json
import os

# --- Configuración desde variables de entorno ---
TOKEN = os.environ.get("TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")

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
        print(f"Telegram: {r.status_code}")
    except Exception as e:
        print(f"Error Telegram: {e}")


def cargar_json(archivo):
    if os.path.exists(archivo):
        with open(archivo, "r") as f:
            return json.load(f)
    return {}


def guardar_json(archivo, data):
    with open(archivo, "w") as f:
        json.dump(data, f)


def buscar_productos(busqueda):
    """Usa ScraperAPI como proxy para evitar el bloqueo de CloudFront."""
    SCRAPER_KEY = os.environ.get("SCRAPER_KEY", "")
    
    target_url = f"https://api.wallapop.com/api/v3/general/search?keywords={busqueda.replace(' ', '%20')}&max_sale_price={PRECIO_MAX}&order_by=newest&country_code=ES"
    
    # Si hay clave de ScraperAPI, usarla como proxy
    if SCRAPER_KEY:
        url = f"https://api.scraperapi.com?api_key={SCRAPER_KEY}&url={target_url}"
        headers = {}
    else:
        # Sin proxy, intentar directamente
        url = target_url
        headers = {
            "User-Agent": "Wallapop/76 CFNetwork/1410.0.3 Darwin/22.6.0",
            "Accept": "application/json",
            "Accept-Language": "es-ES",
            "X-DeviceOS": "0",
            "X-AppVersion": "76",
        }

    productos = []
    try:
        r = requests.get(url, headers=headers, timeout=60)
        print(f"API Wallapop [{busqueda}]: status {r.status_code}")

        if r.status_code != 200:
            print(f"  Error: {r.text[:200]}")
            return productos

        data = r.json()
        items = data.get("search_objects", data.get("data", []))
        print(f"  → {len(items)} productos encontrados")

        for item in items:
            try:
                id_prod = str(item.get("id", ""))
                titulo = item.get("title", "Sin título")
                precio = float(item.get("sale_price", 0))
                slug = item.get("web_slug", "")
                url_prod = f"https://es.wallapop.com/item/{slug}" if slug else "https://es.wallapop.com"

                if precio <= PRECIO_MAX and id_prod:
                    productos.append((id_prod, titulo, precio, url_prod))
            except:
                continue

    except Exception as e:
        print(f"Error buscando '{busqueda}': {e}")

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
                print(f"✅ Nuevo: {titulo[:50]} - {precio}€")

    guardar_json(ARCHIVO_IDS, enviados)
    guardar_json(ARCHIVO_CATALOGO, catalogo)


indice_periodico = {b: 0 for b in BUSQUEDAS}


def ciclo_periodico():
    catalogo = cargar_json(ARCHIVO_CATALOGO)
    for busqueda in BUSQUEDAS:
        productos = catalogo.get(busqueda, [])
        if not productos:
            print(f"📭 Sin productos para '{busqueda}'")
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
    print(f"   Intervalo: {SLEEP_TIME}s | Periódico: {ENVIO_PERIODICO}s")

    ultimo_periodico = time.time()

    while True:
        ciclo_nuevos()

        if time.time() - ultimo_periodico >= ENVIO_PERIODICO:
            print("📬 Envío periódico...")
            ciclo_periodico()
            ultimo_periodico = time.time()

        print(f"⏳ Esperando {SLEEP_TIME}s...")
        time.sleep(SLEEP_TIME)
