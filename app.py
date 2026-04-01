import os
import uvicorn
import requests
from fastapi import FastAPI, Request
from openai import OpenAI
# --- NUEVAS LIBRERÍAS ---
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta

print("🚀 APP.PY CARGADO CORRECTAMENTE - VERSIÓN AGENDADOR 🚀")

app = FastAPI()

# =========================
# VARIABLES Y GOOGLE CONFIG
# =========================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "").strip()
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "").strip()
INSTANCE_NAME = os.getenv("INSTANCE_NAME", "Flowganters").strip()

SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_FILE = 'credentials.json' # Asegúrate de que este archivo esté en tu carpeta

client = OpenAI(api_key=OPENAI_API_KEY)

# =========================
# FUNCIONES DE GOOGLE CALENDAR
# =========================
def get_calendar_service():
    try:
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        return build('calendar', 'v3', credentials=creds)
    except Exception as e:
        print(f"❌ Error conectando a Google: {e}")
        return None

def agendar_en_google(resumen, fecha_iso):
    print(f"📅 Intentando agendar: {resumen} para {fecha_iso}")
    try:
        service = get_calendar_service()
        if not service: return False
        
        # Limpiar la fecha y definir fin (1 hora después)
        inicio_dt = datetime.fromisoformat(fecha_iso.replace('Z', ''))
        fin_dt = inicio_dt + timedelta(hours=1)
        
        evento = {
            'summary': resumen,
            'description': 'Agendado automáticamente por Flowganters AI',
            'start': {'dateTime': inicio_dt.isoformat(), 'timeZone': 'America/Santo_Domingo'},
            'end': {'dateTime': fin_dt.isoformat(), 'timeZone': 'America/Santo_Domingo'},
        }
        
        service.events().insert(calendarId='primary', body=evento).execute()
        print("✅ Cita guardada en Google Calendar")
        return True
    except Exception as e:
        print(f"❌ Error al crear evento: {e}")
        return False

# =========================
# WEBHOOK
# =========================
@app.post("/webhook")
async def receive_message(request: Request):
    try:
        data = await request.json()
        msg_data = data.get("data", {})
        
        if msg_data.get("key", {}).get("fromMe"): return {"status": "ignored"}

        # Extraer texto y número
        message_obj = msg_data.get("message", {})
        user_text = message_obj.get("conversation") or message_obj.get("extendedTextMessage", {}).get("text")
        remote_number = msg_data.get("key", {}).get("remoteJid", "").split("@")[0]

        if not user_text: return {"status": "no_text"}

        # 1. Obtener respuesta de la IA
        ai_response = get_ai_response(user_text)

        # 2. LÓGICA DE AGENDAMIENTO: Si la IA confirma, ejecutamos Google
        if "CONFIRMADO:" in ai_response:
            try:
                # Esperamos algo como: "CONFIRMADO: Juan Perez el 2026-04-01T15:00:00"
                datos = ai_response.split("CONFIRMADO:")[1].strip()
                nombre_cita, fecha_cita = datos.split(" el ")
                
                if agendar_en_google(f"Cita: {nombre_cita}", fecha_cita):
                    ai_response = f"¡Perfecto {nombre_cita}! 🦷 Tu cita ha sido agendada para el {fecha_cita}. ¡Te esperamos!"
                else:
                    ai_response = "Tuve un problema con mi agenda, pero un humano te confirmará en breve. 🙏"
            except:
                print("⚠️ Error procesando el formato de confirmación de la IA")

        # 3. Enviar a WhatsApp
        send_to_whatsapp(remote_number, ai_response)
        return {"status": "success"}

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return {"status": "error"}

# =========================
# OPENAI ACTUALIZADO
# =========================
def get_ai_response(user_input):
    prompt_sistema = """Eres el asistente de la clínica dental Flowganters. 
    Tu meta es agendar citas. Sé amable y profesional 🦷.
    
    INSTRUCCIONES DE AGENDAMIENTO:
    1. Si el usuario quiere una cita, pídele nombre y fecha/hora específica.
    2. Cuando el usuario te dé los datos, responde EXACTAMENTE así para que el sistema procese:
       'CONFIRMADO: [Nombre del Paciente] el [Fecha en formato YYYY-MM-DDTHH:MM:SS]'
    3. Si no hay datos completos, sigue conversando normalmente."""

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": user_input}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        return "¡Hola! 🦷 ¿Te gustaría agendar una cita?"

# =========================
# EVOLUTION API (Mismo que ya tienes)
# =========================
def send_to_whatsapp(to_number, text):
    url = f"{EVOLUTION_API_URL.rstrip('/')}/message/sendText/{INSTANCE_NAME}"
    headers = {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}
    payload = {"number": to_number, "text": text, "delay": 500}
    requests.post(url, json=payload, headers=headers)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)