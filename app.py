import os
import uvicorn
import requests
import json
from fastapi import FastAPI, Request
from openai import OpenAI
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta

app = FastAPI()

print("🚀 APP.PY CARGADO CORRECTAMENTE - VERSIÓN SEGURA 3.0 🚀")

# =========================
# VARIABLES Y CONFIG
# =========================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "").strip()
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "").strip()
INSTANCE_NAME = os.getenv("INSTANCE_NAME", "Flowganters").strip()

# Archivo local para pruebas, en Railway usaremos la Variable de Entorno
SERVICE_ACCOUNT_FILE = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/calendar']

client = OpenAI(api_key=OPENAI_API_KEY)

# =========================
# FUNCIONES AUXILIARES
# =========================
def get_calendar_service():
    try:
        # 1. Intentamos cargar desde la variable de Railway (Nube)
        creds_json = os.getenv("GOOGLE_CREDS_JSON")
        
        if creds_json:
            info = json.loads(creds_json)
            creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
            print("✅ Conectado usando Variable de Entorno")
        else:
            # 2. Si no existe (Local), usamos el archivo credentials.json
            creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
            print("🏠 Conectado usando archivo local")
            
        return build('calendar', 'v3', credentials=creds)
    except Exception as e:
        print(f"❌ Error Google Service: {e}")
        return None

def agendar_en_google(resumen, fecha_iso):
    try:
        service = get_calendar_service()
        if not service: return False
        
        inicio_dt = datetime.fromisoformat(fecha_iso)
        fin_dt = inicio_dt + timedelta(hours=1)
        
        evento = {
            'summary': resumen,
            'start': {'dateTime': inicio_dt.isoformat(), 'timeZone': 'America/Santo_Domingo'},
            'end': {'dateTime': fin_dt.isoformat(), 'timeZone': 'America/Santo_Domingo'},
        }
        service.events().insert(calendarId='primary', body=evento).execute()
        return True
    except Exception as e:
        print(f"❌ Error insertando evento: {e}")
        return False

# =========================
# RUTAS (WEBHOOK)
# =========================
@app.get("/")
def home():
    return {"status": "ok", "message": "Flowganters AI está vivo y seguro"}

@app.post("/webhook")
async def receive_message(request: Request):
    try:
        data = await request.json()
        msg_data = data.get("data", {})
        if msg_data.get("key", {}).get("fromMe"): return {"status": "ignored"}

        message_obj = msg_data.get("message", {})
        user_text = message_obj.get("conversation") or message_obj.get("extendedTextMessage", {}).get("text")
        remote_number = msg_data.get("key", {}).get("remoteJid", "").split("@")[0]

        if not user_text: return {"status": "no_text"}

        ai_response = get_ai_response(user_text)

        # LÓGICA DE AGENDAMIENTO
        if "CONFIRMADO:" in ai_response:
            try:
                datos = ai_response.split("CONFIRMADO:")[1].strip()
                nombre_cita, resto = datos.split(" el ")
                fecha_cita = resto.strip()[:19] 
                
                if "YYYY" in fecha_cita or "MM" in fecha_cita:
                    print("⚠️ Formato inválido detectado (ejemplo literal).")
                else:
                    if agendar_en_google(f"Cita: {nombre_cita}", fecha_cita):
                        print(f"✅ Cita agendada: {nombre_cita} para {fecha_cita}")
            except Exception as e:
                print(f"⚠️ Error procesando cita: {e}")

        send_to_whatsapp(remote_number, ai_response)
        return {"status": "success"}
    except Exception as e:
        print(f"❌ Error Webhook: {e}")
        return {"status": "error"}

# =========================
# INTELIGENCIA ARTIFICIAL
# =========================
def get_ai_response(user_input):
    try:
        hoy = datetime.now().strftime("%Y-%m-%d %H:%M")
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system", 
                    "content": f"""Eres el asistente de la clínica dental Flowganters. Hoy es {hoy}.
                    Cuando agendes, confirma usando EXACTAMENTE este formato:
                    'CONFIRMADO: [Nombre] el [FECHA EN FORMATO ISO]'
                    Ejemplo: CONFIRMADO: Juan el 2026-04-01T15:00:00"""
                },
                {"role": "user", "content": user_input}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"❌ Error OpenAI: {e}")
        return "Lo siento, ¿podrías repetirme la fecha y hora?"

# =========================
# ENVÍO WHATSAPP
# =========================
def send_to_whatsapp(to_number, text):
    url = f"{EVOLUTION_API_URL.rstrip('/')}/message/sendText/{INSTANCE_NAME}"
    headers = {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}
    payload = {"number": to_number, "text": text}
    requests.post(url, json=payload, headers=headers)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)