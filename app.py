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

print("🚀 APP.PY CARGADO - VERSIÓN MULTILENGUAJE 3.6 🚀")

# =========================
# VARIABLES Y CONFIG
# =========================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "").strip()
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "").strip()
INSTANCE_NAME = os.getenv("INSTANCE_NAME", "Flowganters").strip()
SCOPES = ['https://www.googleapis.com/auth/calendar']

client = OpenAI(api_key=OPENAI_API_KEY)

# =========================
# FUNCIONES AUXILIARES
# =========================
def get_calendar_service():
    try:
        creds_json = os.getenv("GOOGLE_CREDS_JSON")
        if creds_json:
            info = json.loads(creds_json)
            creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        else:
            creds = service_account.Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
        return build('calendar', 'v3', credentials=creds)
    except Exception as e:
        print(f"❌ Error Google Service: {e}")
        return None

def agendar_en_google(resumen, fecha_iso, telefono_cliente):
    try:
        service = get_calendar_service()
        if not service: return False
        
        inicio_dt = datetime.fromisoformat(fecha_iso)
        fin_dt = inicio_dt + timedelta(hours=1)
        
        evento = {
            'summary': resumen,
            'description': f"Cita agendada vía WhatsApp\nTeléfono: {telefono_cliente}",
            'start': {'dateTime': inicio_dt.isoformat(), 'timeZone': 'America/Santo_Domingo'},
            'end': {'dateTime': fin_dt.isoformat(), 'timeZone': 'America/Santo_Domingo'},
        }
        # Cambia 'primary' por tu email si quieres verlo en tu calendario personal
        service.events().insert(calendarId='primary', body=evento).execute()
        return True
    except Exception as e:
        print(f"❌ Error insertando evento: {e}")
        return False

# =========================
# RUTAS (WEBHOOK)
# =========================
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

        # Si la IA genera el comando técnico, procesamos el agendamiento
        if "CONFIRMADO:" in ai_response:
            try:
                # Extraemos la parte técnica
                parts = ai_response.split("CONFIRMADO:")
                texto_previo = parts[0].strip() # Mensaje amable en el idioma del usuario
                datos_tecnicos = parts[1].strip()
                
                nombre_cita, resto = datos_tecnicos.split(" el ")
                fecha_cita = resto.strip()[:19] 
                
                if agendar_en_google(f"Cita: {nombre_cita}", fecha_cita, remote_number):
                    dt_obj = datetime.fromisoformat(fecha_cita)
                    fecha_legible = dt_obj.strftime("%d/%m/%Y")
                    hora_legible = dt_obj.strftime("%I:%M %p")
                    
                    # Si la IA envió un texto previo, lo usamos, si no, usamos un recap estándar
                    if texto_previo:
                        ai_response = f"{texto_previo}\n\n👤 *{nombre_cita}*\n📅 *{fecha_legible}*\n⏰ *{hora_legible}*\n📱 *{remote_number}*"
                    else:
                        # Fallback por si la IA solo envió el comando
                        ai_response = f"✅ Done! / ¡Listo!\n\n👤 *{nombre_cita}*\n📅 *{fecha_legible}*\n⏰ *{hora_legible}*"
                    
                    print(f"📅 Cita agendada para {nombre_cita}")
            except Exception as e:
                print(f"⚠️ Error procesando confirmación: {e}")

        send_to_whatsapp(remote_number, ai_response)
        return {"status": "success"}
    except Exception as e:
        print(f"❌ Error Webhook: {e}")
        return {"status": "error"}

@app.get("/")
def home(): return {"status": "online"}

# =========================
# IA - MODO ASISTENTE MULTILENGUAJE
# =========================
def get_ai_response(user_input):
    try:
        hoy = datetime.now().strftime("%Y-%m-%d %H:%M")
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system", 
                    "content": f"""Eres el asistente de la clínica Flowganters. Hoy es {hoy}.
                    
                    REGLAS DE IDIOMA:
                    - Responde SIEMPRE en el mismo idioma que te hable el usuario (Español, Inglés, etc).
                    
                    INSTRUCCIONES:
                    1. Saluda amablemente.
                    2. Si faltan datos (Nombre, Fecha u Hora), pídelos educadamente en su idioma.
                    3. Si ya tienes Nombre y Fecha/Hora, responde con un mensaje de éxito en su idioma seguido INMEDIATAMENTE del comando técnico:
                       
                       Ejemplo (si es inglés): 'Great! Your appointment is set. CONFIRMADO: John Doe el 2026-04-02T15:00:00'
                       Ejemplo (si es español): '¡Perfecto! Cita agendada. CONFIRMADO: Juan Perez el 2026-04-02T15:00:00'
                    
                    No pidas el número de teléfono."""
                },
                {"role": "user", "content": user_input}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content
    except:
        return "Sorry, could you repeat that? / Lo siento, ¿podrías repetir los datos?"

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