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

print("🚀 APP.PY CARGADO - VERSIÓN AGENDADOR CON RECAP 3.5 🚀")

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
        
        # Extraemos el número de teléfono del remitente
        remote_number = msg_data.get("key", {}).get("remoteJid", "").split("@")[0]

        if not user_text: return {"status": "no_text"}

        ai_response = get_ai_response(user_text)

        # Si la IA genera el comando técnico, agendamos
        if "CONFIRMADO:" in ai_response:
            try:
                datos = ai_response.split("CONFIRMADO:")[1].strip()
                nombre_cita, resto = datos.split(" el ")
                fecha_cita = resto.strip()[:19] 
                
                # Pasamos el remote_number para guardarlo en el calendario
                if agendar_en_google(f"Cita: {nombre_cita}", fecha_cita, remote_number):
                    dt_obj = datetime.fromisoformat(fecha_cita)
                    fecha_legible = dt_obj.strftime("%d/%m/%Y")
                    hora_legible = dt_obj.strftime("%I:%M %p")
                    
                    # RECAP EN EL CHAT
                    ai_response = (
                        f"✅ *¡CITA AGENDADA CON ÉXITO!*\n\n"
                        f"Aquí tienes el resumen de tu cita:\n"
                        f"👤 *Paciente:* {nombre_cita}\n"
                        f"📅 *Fecha:* {fecha_legible}\n"
                        f"⏰ *Hora:* {hora_legible}\n"
                        f"📱 *Teléfono:* {remote_number}\n\n"
                        f"¡Te esperamos en Flowganters! 🦷"
                    )
                    print(f"📅 Recap enviado a {nombre_cita}")
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
# IA - MODO ASISTENTE
# =========================
def get_ai_response(user_input):
    try:
        hoy = datetime.now().strftime("%Y-%m-%d %H:%M")
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system", 
                    "content": f"""Eres el asistente virtual de la clínica dental Flowganters. Hoy es {hoy}.
                    
                    INSTRUCCIONES:
                    1. Saluda amablemente si el usuario saluda.
                    2. Si faltan datos (Nombre o Fecha/Hora), pide: 'Nombre completo, Fecha y Hora'.
                    3. Si ya tienes Nombre y Fecha/Hora, responde SOLO con el formato técnico de abajo.
                    
                    FORMATO TÉCNICO:
                    CONFIRMADO: [Nombre] el [FECHA ISO]"""
                },
                {"role": "user", "content": user_input}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content
    except:
        return "Lo siento, ¿podrías enviarme tu nombre, fecha y hora para agendar?"

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