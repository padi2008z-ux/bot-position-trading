import os
import time
import threading
from datetime import datetime
from zoneinfo import ZoneInfo
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
import yfinance as yf

# ==========================================
# SERVIDOR WEB SIMULADO (Render 24/7)
# ==========================================
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Bot Position Trading activo y funcionando 24/7")

def start_dummy_server():
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), DummyHandler)
    server.serve_forever()

# ==========================================
# CONFIGURACIÓN DEL BOT
# ==========================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Lista idéntica de 53 activos
TICKERS = {
    # --- ESPAÑA (Mercado Continuo / IBEX 35) ---
    "ACC.MC": "Acciona",
    "ADX.MC": "Audax Renovables",
    "AMS.MC": "Amadeus",
    "AMP.MC": "Amper",
    "ACS.MC": "ACS",
    "ATRY.MC": "Atrys Health",
    "CABK.MC": "CaixaBank",
    "CAF.MC": "Construcciones y Auxiliar de Ferrocarriles",
    "EZE.MC": "Ezentis",
    "GRF.MC": "Grifols",
    "IAG.MC": "IAG (Iberia)",
    "IBE.MC": "Iberdrola",
    "REP.MC": "Repsol",
    "SAN.MC": "Banco Santander",
    "SCYR.MC": "Sacyr",

    # --- ESTADOS UNIDOS ---
    "AAPL": "Apple",
    "AMZN": "Amazon",
    "AVGO": "Broadcom",
    "BABA": "Alibaba",
    "BMY": "Bristol-Myers Squibb",
    "BSX": "Boston Scientific",
    "CW": "Curtiss-Wright",
    "GFS": "GlobalFoundries",
    "GE": "GE Aerospace",
    "IBM": "IBM",
    "INTU": "Intuit",
    "IONQ": "IonQ",
    "LNG": "Cheniere Energy",
    "MELI": "MercadoLibre",
    "META": "Meta (Facebook)",
    "MT": "ArcelorMittal",
    "MTCH": "Match Group",
    "NFLX": "Netflix",
    "NVDA": "NVIDIA",
    "ORCL": "Oracle",
    "PLTR": "Palantir",
    "PODD": "Insulet",
    "PYPL": "PayPal",
    "SNAP": "Snapchat",
    "SOFI": "SoFi Technologies",
    "SYF": "Synchrony Financial",
    "TEM": "Tempus AI",
    "TSLA": "Tesla",

    # --- EUROPA ---
    "AIR.PA": "Airbus",
    "ALO.PA": "Alstom",
    "ATCO-A.ST": "Atlas Copco (A)",
    "ATCO-B.ST": "Atlas Copco (B)",
    "BFSA.DE": "Befesa",
    "CMB.MI": "Cembre S.p.A.",
    "CSU.TO": "Constellation Software",
    "FRE.DE": "Fresenius",
    "HO.PA": "Thales",
    "MTX.DE": "MTU Aero Engines",
    "NDX1.DE": "Nordex",
    "NOVN.SW": "Novartis",
    "RR.L": "Rolls-Royce",
    "SAN.PA": "Sanofi",
    "SU.PA": "Schneider Electric",
    "VBK.DE": "VERBIO",
    "RHM.DE": "Rheinmetall",

    # --- CRIPTO & ETFs ---
    "BTC-USD": "Bitcoin",
    "GOAI.DE": "ETF MSCI Robotics & AI",
    "EXX6.DE": "ETF IBEX 35"
}

# Parámetros Position Trading
MEDIA_RAPIDA = 50   # SMA 50 días
MEDIA_LENTA = 200  # SMA 200 días

estado_anterior = {}
fecha_ultimo_saludo = ""

def enviar_telegram(mensaje):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Error: No se han configurado TELEGRAM_TOKEN o CHAT_ID")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"Error enviando mensaje a Telegram: {e}")

def comprobar_saludo_diario():
    global fecha_ultimo_saludo
    try:
        zona_esp = ZoneInfo("Europe/Madrid")
        ahora_esp = datetime.now(zona_esp)
        fecha_hoy = ahora_esp.strftime("%Y-%m-%d")

        if ahora_esp.hour == 8 and fecha_ultimo_saludo != fecha_hoy:
            msg = "☀️ *¡Buenos días!* Bot de Position Trading (SMA 50/200) activo."
            enviar_telegram(msg)
            fecha_ultimo_saludo = fecha_hoy
    except Exception as e:
        print(f"Error en saludo diario: {e}")

def evaluar_cruce_medias():
    comprobar_saludo_diario()
    print(f"🔍 Evaluando cruce SMA{MEDIA_RAPIDA}/SMA{MEDIA_LENTA} (Velas Diarias)...")
    ticker_list = list(TICKERS.keys())

    try:
        # Descarga 1 año de datos diarios
        datos = yf.download(ticker_list, period="1y", interval="1d", progress=False)
    except Exception as e:
        print(f"Error descargando datos del mercado: {e}")
        return

    for ticker, nombre in TICKERS.items():
        try:
            df = datos.xs(ticker, level=1, axis=1) if len(ticker_list) > 1 else datos
            df = df.dropna(subset=['Close'])

            if len(df) < MEDIA_LENTA + 1:
                continue

            # Cálculo de Medias Móviles Simples
            df['SMA_Fast'] = df['Close'].rolling(window=MEDIA_RAPIDA).mean()
            df['SMA_Slow'] = df['Close'].rolling(window=MEDIA_LENTA).mean()

            fast_ayer = float(df['SMA_Fast'].iloc[-2])
            slow_ayer = float(df['SMA_Slow'].iloc[-2])

            fast_hoy = float(df['SMA_Fast'].iloc[-1])
            slow_hoy = float(df['SMA_Slow'].iloc[-1])

            precio_actual = float(df['Close'].iloc[-1])

            # 1. SEÑAL DE COMPRA (Golden Cross)
            if fast_ayer <= slow_ayer and fast_hoy > slow_hoy:
                if estado_anterior.get(ticker) != "BUY":
                    msg = (
                        f"🟢 *SEÑAL DE COMPRA (POSITION TRADING)*\n"
                        f"*Empresa:* *{nombre}* (`{ticker}`)\n"
                        f"*Precio actual:* `{precio_actual:.2f}`\n"
                        f"*Cruce:* SMA{MEDIA_RAPIDA} (`{fast_hoy:.2f}`) cruzó por ENCIMA de SMA{MEDIA_LENTA} (`{slow_hoy:.2f}`)"
                    )
                    enviar_telegram(msg)
                    estado_anterior[ticker] = "BUY"

            # 2. SEÑAL DE VENTA (Death Cross)
            elif fast_ayer >= slow_ayer and fast_hoy < slow_hoy:
                if estado_anterior.get(ticker) != "SELL":
                    msg = (
                        f"🔴 *SEÑAL DE VENTA / SALIDA (POSITION TRADING)*\n"
                        f"*Empresa:* *{nombre}* (`{ticker}`)\n"
                        f"*Precio actual:* `{precio_actual:.2f}`\n"
                        f"*Cruce:* SMA{MEDIA_RAPIDA} (`{fast_hoy:.2f}`) cruzó por DEBAJO de SMA{MEDIA_LENTA} (`{slow_hoy:.2f}`)"
                    )
                    enviar_telegram(msg)
                    estado_anterior[ticker] = "SELL"

        except Exception as e:
            print(f"Error procesando {ticker}: {e}")

if __name__ == "__main__":
    t = threading.Thread(target=start_dummy_server, daemon=True)
    t.start()

    enviar_telegram("🤖 *Bot Position Trading Activado*\nMonitoreando cruce de SMA 50 / SMA 200 en temporalidad diaria.")
    while True:
        evaluar_cruce_medias()
        time.sleep(7200)  # Revisa cada 2 horas
