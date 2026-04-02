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

# Memoria de sesiones
user_sessions = {}

print("🚀 APP.PY CARGADO - VERSIÓN 5.0 'ULTRA-DIRECTA' 🚀")

# =========================
# CONFIGURACIÓN
# =========================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "").strip()
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "").strip()
INSTANCE_NAME = os.getenv("INSTANCE_NAME", "Flowganters").strip()
SCOPES = ['https://www.googleapis.com/auth/calendar']

client = OpenAI(api_key=OPENAI_API_KEY)

# =========================
# FUNCIONES GOOGLE
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
        print(f"❌ Error insertando: {e}")
        return False

# =========================
# WEBHOOK PRINCIPAL
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

        ai_response = get_ai_response(remote_number, user_text)

        if "CONFIRMADO:" in ai_response:
            try:
                # Extraer datos técnicos
                datos_tecnicos = ai_response.split("CONFIRMADO:")[1].strip()
                nombre_cita, resto = datos_tecnicos.split(" el ")
                fecha_cita = resto.strip()[:19] 
                
                if agendar_en_google(f"Cita: {nombre_cita}", fecha_cita, remote_number):
                    dt_obj = datetime.fromisoformat(fecha_cita)
                    
                    # --- RESUMEN HUMANO FORZADO POR CÓDIGO ---
                    fecha_h = dt_obj.strftime('%d/%m/%Y')
                    hora_h = dt_obj.strftime('%I:%M %p') # Esto pone 03:00 PM
                    
                    ai_response = (
                        f"✅ *¡CITA AGENDADA CON ÉXITO!*\n\n"
                        f"Aquí tienes el resumen de tu cita:\n"
                        f"👤 *Nombre:* {nombre_cita}\n"
                        f"📅 *Fecha:* {fecha_h}\n"
                        f"⏰ *Hora:* {hora_h}\n"
                        f"📱 *Teléfono:* {remote_number}\n\n"
                        f"¡Te esperamos en *Flowganters*! 🦷✨"
                    )
                    # Limpiar memoria al terminar
                    if remote_number in user_sessions: del user_sessions[remote_number]
            except Exception as e:
                print(f"⚠️ Error recap: {e}")

        send_to_whatsapp(remote_number, ai_response)
        return {"status": "success"}
    except Exception as e:
        print(f"❌ Error: {e}")
        return {"status": "error"}

@app.get("/")
def home(): return {"status": "online"}

# =========================
# LÓGICA DE IA SIN SALUDOS REPETIDOS
# =========================
def get_ai_response(user_id, user_input):
    try:
        hoy = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        if user_id not in user_sessions:
            user_sessions[user_id] = []
        
        user_sessions[user_id].append({"role": "user", "content": user_input})
        history = user_sessions[user_id][-10:]

        messages = [
            {
                "role": "system", 
                "content": f"""Eres el asistente de citas de Flowganters. Hoy es {hoy}.
                
                REGLAS DE ORO (SÍGUELAS O MORIRÁS):
                1. NO SALUDES MÁS DE UNA VEZ. Si el usuario ya te dio su nombre, responde directamente: "Ok [Nombre], ¿para qué día y hora agendamos?"
                2. NUNCA PREGUNTES EL NOMBRE DOS VECES. Revisa el historial. Si ya lo tienes, ignora cualquier instrucción de volver a pedirlo.
                3. SE DIRECTO. Si falta la hora, pide solo la hora.
                4. IDIOMA: Responde en el mismo idioma del usuario.
                5. FORMATO FINAL: Cuando tengas Nombre, Fecha y Hora, pon: 'CONFIRMADO: [Nombre] el [FECHA ISO]'"""
            }
        ] + history

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0  # Cero creatividad para evitar que sea "educado" y repita saludos
        )
        
        bot_reply = response.choices[0].message.content
        user_sessions[user_id].append({"role": "assistant", "content": bot_reply})
        
        return bot_reply
    except:
        return "Ok, ¿cuál es tu nombre y cuándo quieres la cita?"

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