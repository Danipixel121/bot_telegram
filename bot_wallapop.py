import requests
import time
import json
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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


def crear_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    driver = webdriver.Chrome(options=options)
    return driver


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


def buscar_productos(driver, busqueda):
    productos = []
    try:
        url = f"https://es.wallapop.com/app/search?keywords={busqueda.replace(' ', '%20')}&order_by=newest&max_sale_price={PRECIO_MAX}"
        driver.get(url)
        time.sleep(5)  # Esperar a que cargue JS

        # Buscar tarjetas de productos
        items = driver.find_elements(By.CSS_SELECTOR, "a[href*='/item/']")
        print(f"  → {len(items)} items encontrados en DOM")

        for item in items:
            try:
                href = item.get_attribute("href")
                if not href or "/item/" not in href:
                    continue
                id_prod = href.split("/item/")[-1].split("?")[0]
                texto = item.text.strip()

                # Buscar precio en el texto
                if "€" in texto:
                    lineas = texto.split("\n")
                    precio = None
                    for linea in lineas:
                        if "€" in linea:
                            try:
                                precio = float(linea.replace("€", "").replace(".", "").replace(",", ".").strip())
                                break
                            except:
                                continue
                    if precio and precio <= PRECIO_MAX and id_prod:
                        titulo = lineas[0] if lineas else "Sin título"
                        productos.append((id_prod, titulo, precio, href))
            except Exception as e:
                continue

    except Exception as e:
        print(f"Error buscando '{busqueda}': {e}")

    return productos


def ciclo_nuevos(driver):
    enviados = cargar_json(ARCHIVO_IDS)
    catalogo = cargar_json(ARCHIVO_CATALOGO)

    for busqueda in BUSQUEDAS:
        print(f"🔍 Buscando: '{busqueda}'")
        productos = buscar_productos(driver, busqueda)

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

    driver = crear_driver()
    ultimo_periodico = time.time()

    try:
        while True:
            ciclo_nuevos(driver)

            if time.time() - ultimo_periodico >= ENVIO_PERIODICO:
                print("📬 Envío periódico...")
                ciclo_periodico()
                ultimo_periodico = time.time()

            print(f"⏳ Esperando {SLEEP_TIME}s...")
            time.sleep(SLEEP_TIME)
    finally:
        driver.quit()
