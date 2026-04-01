import os
import uvicorn
import requests
from fastapi import FastAPI, Request
from openai import OpenAI

print("🚀 APP.PY CARGADO CORRECTAMENTE 🚀")

app = FastAPI()

# =========================
# VARIABLES DE ENTORNO
# =========================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "").strip()
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "").strip()
INSTANCE_NAME = os.getenv("INSTANCE_NAME", "Flowganters").strip()

print("🔑 OPENAI_API_KEY cargada:", "Sí" if OPENAI_API_KEY else "No")
print("📡 EVOLUTION_API_URL:", EVOLUTION_API_URL if EVOLUTION_API_URL else "NO CONFIGURADA")
print("🔐 EVOLUTION_API_KEY cargada:", "Sí" if EVOLUTION_API_KEY else "No")
print("📱 INSTANCE_NAME:", INSTANCE_NAME)

client = OpenAI(api_key=OPENAI_API_KEY)

# =========================
# ROOT
# =========================
@app.get("/")
def home():
    print("🔥🔥🔥 ROOT EJECUTADO DESDE APP.PY CORRECTO 🔥🔥🔥")
    return {"status": "ok", "server": "Flowganters AI Online"}

# =========================
# WEBHOOK
# =========================
@app.post("/webhook")
async def receive_message(request: Request):
    print("🔥🔥🔥 NUEVA PETICIÓN RECIBIDA EN /WEBHOOK 🔥🔥🔥")
    try:
        data = await request.json()
        print(f"📦 JSON RECIBIDO: {data}")

        event_type = data.get("event")
        print(f"📌 EVENT TYPE: {event_type}")

        if event_type in ["messages.upsert", "messages.set"]:
            msg_data = data.get("data", {})
            print(f"🧩 MSG DATA: {msg_data}")

            # 1. Ignorar mensajes enviados por el propio bot
            if msg_data.get("key", {}).get("fromMe", False):
                print("⏭️ Ignorado: Mensaje enviado por el propio bot.")
                return {"status": "ignored"}

            # 2. Extraer texto del mensaje
            message_obj = msg_data.get("message", {})
            user_text = (
                message_obj.get("conversation")
                or message_obj.get("extendedTextMessage", {}).get("text")
                or msg_data.get("content")
            )

            # 3. Extraer número limpio
            full_jid = msg_data.get("key", {}).get("remoteJid", "")
            remote_number = full_jid.split("@")[0]

            print(f"📞 full_jid: {full_jid}")
            print(f"📞 remote_number limpio: {remote_number}")
            print(f"💬 user_text detectado: {user_text}")

            if not user_text:
                print(f"⚠️ No hay texto legible de {remote_number}")
                return {"status": "no_text"}

            print(f"📩 PROCESANDO: {remote_number} dice: {user_text}")

            # 4. Generar respuesta con OpenAI
            ai_response = get_ai_response(user_text)
            print(f"🤖 RESPUESTA GPT: {ai_response}")

            # 5. Enviar respuesta a WhatsApp
            send_to_whatsapp(remote_number, ai_response)

            return {"status": "success"}

        print(f"ℹ️ Evento no procesado: {event_type}")
        return {"status": "not_upsert"}

    except Exception as e:
        print(f"❌ ERROR CRÍTICO EN /WEBHOOK: {e}")
        return {"status": "error", "message": str(e)}

# =========================
# OPENAI
# =========================
def get_ai_response(user_input):
    print("🧠 Entrando a get_ai_response()")
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "Eres el asistente dental de Flowganters. Sé amable, profesional y ayuda a agendar citas 🦷."
                },
                {"role": "user", "content": user_input}
            ]
        )
        reply = response.choices[0].message.content
        print("✅ OpenAI respondió correctamente")
        return reply

    except Exception as e:
        print(f"❌ Error OpenAI: {e}")
        return "¡Hola! 🦷 ¿Te gustaría agendar una cita en Flowganters?"

# =========================
# EVOLUTION API
# =========================
def send_to_whatsapp(to_number, text):
    print("📤 Entrando a send_to_whatsapp()")

    url = f"{EVOLUTION_API_URL.rstrip('/')}/message/sendText/{INSTANCE_NAME}"
    headers = {
        "apikey": EVOLUTION_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "number": to_number,
        "text": text,
        "delay": 1000
    }

    print(f"🌐 URL de envío: {url}")
    print(f"📨 Payload de envío: {payload}")

    try:
        res = requests.post(url, json=payload, headers=headers)
        print(f"📤 STATUS ENVÍO A WHATSAPP ({to_number}): {res.status_code}")
        print(f"📤 RESPUESTA EVOLUTION: {res.text}")
    except Exception as e:
        print(f"❌ ERROR DE ENVÍO A WHATSAPP: {e}")

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 Iniciando servidor en puerto {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)