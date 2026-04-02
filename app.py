import os
import uvicorn
import requests
import json
import re
from fastapi import FastAPI, Request
from openai import OpenAI
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta

app = FastAPI()

# =========================
# MEMORIA DE SESIONES
# =========================
user_sessions = {}

print("🚀 APP.PY CARGADO - VERSIÓN 6.0 'PROFESSIONAL RECEPTIONIST' 🚀")

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
        if not service:
            return False

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
        print(f"❌ Error insertando en Google Calendar: {e}")
        return False

# =========================
# UTILIDADES
# =========================
def detectar_nombre_en_historial(history):
    """
    Busca si el usuario ya dijo su nombre en mensajes anteriores.
    """
    texto_total = " ".join(
        msg["content"] for msg in history if msg["role"] == "user"
    )

    patrones = [
        r"\bmi nombre es\s+([A-Za-zÁÉÍÓÚáéíóúñÑ ]+)",
        r"\bme llamo\s+([A-Za-zÁÉÍÓÚáéíóúñÑ ]+)",
        r"\bsoy\s+([A-Za-zÁÉÍÓÚáéíóúñÑ ]+)",
        r"\bmy name is\s+([A-Za-z ]+)",
        r"\bi am\s+([A-Za-z ]+)",
        r"\bit's\s+([A-Za-z ]+)",
    ]

    for patron in patrones:
        match = re.search(patron, texto_total, re.IGNORECASE)
        if match:
            nombre = match.group(1).strip()
            return nombre.title()

    return None

def detectar_idioma_preferido(history):
    """
    Mantiene el idioma base del usuario.
    No cambia a otro idioma a menos que el cliente lo haga claramente.
    """
    texto_total = " ".join(
        msg["content"] for msg in history if msg["role"] == "user"
    ).lower()

    palabras_es = ["hola", "quiero", "cita", "mañana", "nombre", "hora", "día", "puedo", "necesito"]
    palabras_en = ["hello", "appointment", "tomorrow", "name", "time", "day", "need", "can i", "schedule"]

    score_es = sum(1 for p in palabras_es if p in texto_total)
    score_en = sum(1 for p in palabras_en if p in texto_total)

    return "es" if score_es >= score_en else "en"

def formatear_fecha_humana(dt_obj, idioma="es"):
    if idioma == "en":
        fecha_h = dt_obj.strftime('%m/%d/%Y')
        hora_h = dt_obj.strftime('%I:%M %p').lstrip("0")
    else:
        fecha_h = dt_obj.strftime('%d/%m/%Y')
        hora_h = dt_obj.strftime('%I:%M %p').lstrip("0")

    return fecha_h, hora_h

# =========================
# WEBHOOK PRINCIPAL
# =========================
@app.post("/webhook")
async def receive_message(request: Request):
    try:
        data = await request.json()
        msg_data = data.get("data", {})

        if msg_data.get("key", {}).get("fromMe"):
            return {"status": "ignored"}

        message_obj = msg_data.get("message", {})
        user_text = (
            message_obj.get("conversation")
            or message_obj.get("extendedTextMessage", {}).get("text")
        )

        remote_number = msg_data.get("key", {}).get("remoteJid", "").split("@")[0]

        if not user_text:
            return {"status": "no_text"}

        ai_response = get_ai_response(remote_number, user_text)

        if "CONFIRMADO:" in ai_response:
            try:
                datos_tecnicos = ai_response.split("CONFIRMADO:")[1].strip()
                nombre_cita, resto = datos_tecnicos.split(" el ")
                fecha_cita = resto.strip()[:19]

                idioma = detectar_idioma_preferido(user_sessions.get(remote_number, []))

                if agendar_en_google(f"Cita: {nombre_cita}", fecha_cita, remote_number):
                    dt_obj = datetime.fromisoformat(fecha_cita)
                    fecha_h, hora_h = formatear_fecha_humana(dt_obj, idioma)

                    if idioma == "en":
                        ai_response = (
                            f"Perfect, {nombre_cita}. Your appointment has been successfully confirmed.\n\n"
                            f"Here is your appointment summary:\n"
                            f"• Name: {nombre_cita}\n"
                            f"• Date: {fecha_h}\n"
                            f"• Time: {hora_h}\n"
                            f"• Phone: {remote_number}\n\n"
                            f"We look forward to seeing you at Flowganters. 🦷"
                        )
                    else:
                        ai_response = (
                            f"Perfecto, {nombre_cita}. Su cita ha quedado confirmada correctamente.\n\n"
                            f"Aquí tiene el resumen de su cita:\n"
                            f"• Nombre: {nombre_cita}\n"
                            f"• Fecha: {fecha_h}\n"
                            f"• Hora: {hora_h}\n"
                            f"• Teléfono: {remote_number}\n\n"
                            f"Será un placer atenderle en Flowganters. 🦷"
                        )

                    if remote_number in user_sessions:
                        del user_sessions[remote_number]

            except Exception as e:
                print(f"⚠️ Error procesando confirmación: {e}")

        send_to_whatsapp(remote_number, ai_response)
        return {"status": "success"}

    except Exception as e:
        print(f"❌ Error: {e}")
        return {"status": "error"}

@app.get("/")
def home():
    return {"status": "online"}

# =========================
# LÓGICA DE IA
# =========================
def get_ai_response(user_id, user_input):
    try:
        hoy = datetime.now().strftime("%Y-%m-%d %H:%M")

        if user_id not in user_sessions:
            user_sessions[user_id] = []

        user_sessions[user_id].append({"role": "user", "content": user_input})
        history = user_sessions[user_id][-10:]

        nombre_detectado = detectar_nombre_en_historial(history)
        idioma_preferido = detectar_idioma_preferido(history)

        if idioma_preferido == "en":
            system_prompt = f"""
You are the appointment assistant for Flowganters dental clinic.
Today is {hoy}.

YOUR ROLE:
You are a polite, professional front-desk receptionist.
You should sound natural, warm, and efficient — never robotic, never too casual.

IMPORTANT RULES:
1. KEEP THE SAME LANGUAGE THE CUSTOMER STARTED WITH.
   - If the user starts in English, stay in English.
   - Do NOT switch to Spanish unless the customer clearly switches.
   - If they use Spanglish, reply mostly in the language they started with.

2. DO NOT ASK FOR THE NAME AGAIN if it has already been provided.
   - If the customer already gave their name, acknowledge it naturally.
   - Example: "Perfect, John. What day and time would you prefer?"

3. DO NOT GREET REPEATEDLY.
   - Greet only once at the beginning of the conversation.

4. SOUND MORE NATURAL, LESS DIRECT.
   - Be concise, but not cold.
   - Example:
     Bad: "Name and time."
     Good: "Of course. May I have your full name and your preferred day and time?"

5. APPOINTMENT FLOW:
   - First get the patient's full name.
   - Then ask for preferred day and time.
   - If one piece is missing, ask only for that missing piece.

6. ONCE YOU HAVE NAME + DATE + TIME:
   output EXACTLY this technical format on the final line only:
   CONFIRMADO: [Name] el [YYYY-MM-DDTHH:MM:SS]

7. BEFORE THAT final line, write a natural professional confirmation message.

Detected patient name: {nombre_detectado if nombre_detectado else "Unknown"}
"""
        else:
            system_prompt = f"""
Eres el asistente de citas de la clínica dental Flowganters.
Hoy es {hoy}.

TU ROL:
Eres una recepcionista profesional, amable y natural.
Debes sonar humana, cordial y eficiente — nunca robótica ni excesivamente seca.

REGLAS IMPORTANTES:
1. MANTÉN EL MISMO IDIOMA EN EL QUE EL CLIENTE EMPEZÓ.
   - Si comenzó en español, responde en español.
   - NO cambies al inglés a menos que el cliente cambie claramente.
   - Si usa Spanglish, responde principalmente en el idioma con el que inició.

2. NO VUELVAS A PEDIR EL NOMBRE si ya fue proporcionado.
   - Si el cliente ya dio su nombre, reconócelo naturalmente.
   - Ejemplo: "Perfecto, Juan. ¿Qué día y hora le gustaría agendar?"

3. NO SALUDES REPETIDAMENTE.
   - Solo saluda una vez al inicio de la conversación.

4. SUENA MÁS NATURAL Y PROFESIONAL.
   - Sé clara, pero no demasiado directa.
   - Ejemplo:
     Mal: "Dime nombre y hora."
     Bien: "Con gusto. ¿Podría indicarme su nombre completo y el día y la hora que le gustaría reservar?"

5. FLUJO DE LA CITA:
   - Primero obtén el nombre completo del paciente.
   - Luego pregunta por el día y la hora.
   - Si falta solo un dato, pide únicamente ese dato.

6. SI YA TIENES EL NOMBRE, NO LO PIDAS OTRA VEZ.
   - Usa frases como:
     "Perfecto, [Nombre]. ¿Qué día y hora le gustaría agendar?"
     o
     "Muy bien, [Nombre]. ¿Podría indicarme qué día le conviene?"

7. CUANDO YA TENGAS Nombre + Fecha + Hora:
   escribe EXACTAMENTE esta línea técnica al final:
   CONFIRMADO: [Nombre] el [YYYY-MM-DDTHH:MM:SS]

8. ANTES de esa línea técnica, escribe una confirmación natural y profesional.

Nombre detectado del paciente: {nombre_detectado if nombre_detectado else "Desconocido"}
"""

        messages = [{"role": "system", "content": system_prompt}] + history

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.3
        )

        bot_reply = response.choices[0].message.content
        user_sessions[user_id].append({"role": "assistant", "content": bot_reply})

        return bot_reply

    except Exception as e:
        print(f"❌ Error IA: {e}")
        return "Con gusto. ¿Podría indicarme su nombre y el día en que desea agendar su cita?"

# =========================
# ENVÍO WHATSAPP
# =========================
def send_to_whatsapp(to_number, text):
    url = f"{EVOLUTION_API_URL.rstrip('/')}/message/sendText/{INSTANCE_NAME}"
    headers = {
        "apikey": EVOLUTION_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "number": to_number,
        "text": text
    }

    try:
        requests.post(url, json=payload, headers=headers)
    except Exception as e:
        print(f"❌ Error enviando a WhatsApp: {e}")

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)