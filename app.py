import os
import uvicorn
import requests
from fastapi import FastAPI, Request
from openai import OpenAI
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta

app = FastAPI()

print("🚀 APP.PY CARGADO CORRECTAMENTE - VERSIÓN AGENDADOR 2.0 🚀")

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

        # LÓGICA DE AGENDAMIENTO
        if "CONFIRMADO:" in ai_response:
            try:
                datos = ai_response.split("CONFIRMADO:")[1].strip()
                nombre_cita, resto = datos.split(" el ")
                fecha_cita = resto.strip()[:19] # Cortamos para evitar puntos o emojis
                
                # VALIDACIÓN: Evitar que agende el texto de ejemplo literal
                if "YYYY" in fecha_cita or "MM" in fecha_cita:
                    print("⚠️ La IA envió un formato de ejemplo. No se agenda.")
                else:
                    if agendar_en_google(f"Cita: {nombre_cita}", fecha_cita):
                        print(f"✅ Cita guardada: {nombre_cita} para {fecha_cita}")
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
        # Le decimos qué día es hoy para que sepa calcular fechas relativas
        hoy = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system", 
                    "content": f"""Eres el asistente de la clínica dental Flowganters. Hoy es {hoy}.
                    Tu meta es agendar citas. Cuando el usuario diga una fecha y hora, confirma usando ESTE FORMATO:
                    'CONFIRMADO: [Nombre] el [FECHA EN FORMATO ISO]'
                    
                    Ejemplo real: CONFIRMADO: Juan el 2026-04-01T15:00:00
                    
                    Nunca respondas con 'YYYY-MM-DD', usa siempre números reales."""
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