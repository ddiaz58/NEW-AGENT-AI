import os
import uvicorn
import requests
from fastapi import FastAPI, Request
from openai import OpenAI
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta

# =========================================================
# 1. ESTA LÍNEA DEBE IR ANTES DE CUALQUIER @app.post
# =========================================================
app = FastAPI()

print("🚀 APP.PY CARGADO CORRECTAMENTE - VERSIÓN AGENDADOR 🚀")

# =========================
# VARIABLES Y CONFIG
# =========================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "").strip()
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "").strip()
INSTANCE_NAME = os.getenv("INSTANCE_NAME", "Flowganters").strip()

client = OpenAI(api_key=OPENAI_API_KEY)
SERVICE_ACCOUNT_FILE = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/calendar']

# =========================
# FUNCIONES AUXILIARES
# =========================
def get_calendar_service():
    try:
        creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
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
    return {"status": "ok", "message": "Flowganters AI está vivo"}

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

        if "CONFIRMADO:" in ai_response:
            try:
                datos = ai_response.split("CONFIRMADO:")[1].strip()
                nombre_cita, resto = datos.split(" el ")
                fecha_cita = resto.strip()[:19] # Limpieza de fecha
                
                if agendar_en_google(f"Cita: {nombre_cita}", fecha_cita):
                    ai_response = f"¡Perfecto {nombre_cita}! 🦷 Tu cita ha sido agendada para el {fecha_cita}."
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
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Eres el asistente de Flowganters. Para agendar usa: 'CONFIRMADO: [Nombre] el YYYY-MM-DDTHH:MM:SS'. Ejemplo: CONFIRMADO: Juan el 2026-04-01T15:00:00"},
                {"role": "user", "content": user_input}
            ]
        )
        return response.choices[0].message.content
    except:
        return "Lo siento, ¿podrías repetirlo?"

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