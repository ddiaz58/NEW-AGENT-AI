# =========================
# WEBHOOK (REEMPLAZA ESTA PARTE)
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

        # --- LÓGICA DE LIMPIEZA DE FECHA MEJORADA ---
        if "CONFIRMADO:" in ai_response:
            try:
                datos = ai_response.split("CONFIRMADO:")[1].strip()
                nombre_cita, resto = datos.split(" el ")
                
                # Limpiamos la fecha: tomamos solo los primeros 19 caracteres (YYYY-MM-DDTHH:MM:SS)
                fecha_sucia = resto.strip()
                fecha_cita = fecha_sucia[:19] 
                
                if agendar_en_google(f"Cita: {nombre_cita}", fecha_cita):
                    ai_response = f"¡Perfecto {nombre_cita}! 🦷 Tu cita ha sido agendada para el {fecha_cita}. ¡Te esperamos!"
                else:
                    ai_response = "Tuve un problema con mi agenda, pero un humano te confirmará en breve. 🙏"
            except Exception as e:
                print(f"⚠️ Error limpiando fecha: {e}")

        send_to_whatsapp(remote_number, ai_response)
        return {"status": "success"}

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return {"status": "error"}

# =========================
# OPENAI (REEMPLAZA EL PROMPT)
# =========================
def get_ai_response(user_input):
    prompt_sistema = """Eres el asistente de Flowganters. 
    IMPORTANTE: Cuando agendes, usa ESTE FORMATO EXACTO:
    'CONFIRMADO: [Nombre] el YYYY-MM-DDTHH:MM:SS'
    No pongas puntos ni emojis inmediatamente después de la fecha."""
    
    # ... (el resto de tu función get_ai_response igual)