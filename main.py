import os
import logging
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8711518982:AAEshDeMsvh9-lTPYa9LgNtOC_kifTJPBbs")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "576402316")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "030e5675b8947cc061f16c79e718ee3c6375ce89f33c0b7ffb824d2f85b5f721")
AGENT_ID = os.environ.get("AGENT_ID", "agent_3201kks4x6b4echvgxrdght0xn2q")
AGENT_PHONE_NUMBER_ID = os.environ.get("AGENT_PHONE_NUMBER_ID", "phnum_8301kkqsspqdedk92txj26vhgw4v")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
pending_calls = {}


def tg_send(text, reply_markup=None):
    payload = {"chat_id": ADMIN_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=10)
    except Exception as e:
        logger.error(f"Telegram send error: {e}")


def tg_answer_callback(callback_id):
    try:
        requests.post(f"{TELEGRAM_API}/answerCallbackQuery", json={"callback_query_id": callback_id}, timeout=5)
    except Exception as e:
        logger.error(f"Answer callback error: {e}")


@app.route("/lead", methods=["POST", "OPTIONS"])
def receive_lead():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    data = request.json or request.form.to_dict()
    logger.info(f"New lead: {data}")

    name = data.get("full_name") or data.get("name", "Unknown")
    phone = data.get("phone", "")
    car = data.get("car_brand") or data.get("vehicle_make", "")
    model = data.get("model", "")
    location = data.get("vehicle_location") or data.get("location", "")
    contact_method = data.get("contact_method", "").lower()

    phone_clean = "".join(filter(str.isdigit, phone))
    if phone_clean and not phone_clean.startswith("1"):
        phone_clean = "1" + phone_clean
    phone_e164 = "+" + phone_clean if phone_clean else phone

    lead_id = phone_clean or name.replace(" ", "")
    pending_calls[lead_id] = {
        "name": name, "phone": phone_e164, "car": car,
        "model": model, "location": location, "contact_method": contact_method
    }

    contact_emoji = "📞" if contact_method == "call" else "💬" if "sms" in contact_method else "💚"
    message = (
        f"🔔 *Новый лид!*\n\n"
        f"👤 *Имя:* {name}\n"
        f"📱 *Телефон:* {phone_e164}\n"
        f"🚗 *Машина:* {car} {model}\n"
        f"📍 *Локация:* {location}\n"
        f"{contact_emoji} *Метод связи:* {contact_method}"
    )

    keyboard = {"inline_keyboard": []}
    if contact_method == "call":
        keyboard["inline_keyboard"].append([{"text": "📞 Позвонить через Alex", "callback_data": f"call_{lead_id}"}])
    keyboard["inline_keyboard"].append([{"text": "✅ Обработан", "callback_data": f"done_{lead_id}"}])

    tg_send(message, keyboard)
    return jsonify({"status": "ok"}), 200


@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    data = request.json
    callback = data.get("callback_query")
    if not callback:
        return jsonify({"status": "ok"}), 200

    callback_id = callback.get("id")
    cb_data = callback.get("data", "")
    tg_answer_callback(callback_id)

    if cb_data.startswith("call_"):
        lead_id = cb_data.replace("call_", "")
        lead = pending_calls.get(lead_id)

        if not lead:
            tg_send("❌ Лид не найден или уже обработан.")
            return jsonify({"status": "ok"}), 200

        tg_send(f"⏳ Звоню {lead['name']} на {lead['phone']}...")

        resp = requests.post(
            "https://api.elevenlabs.io/v1/convai/twilio/outbound-call",
            headers={"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"},
            json={
                "agent_id": AGENT_ID,
                "agent_phone_number_id": AGENT_PHONE_NUMBER_ID,
                "to_number": lead["phone"],
                "conversation_initiation_client_data": {
                    "dynamic_variables": {
                        "customer_name": lead["name"],
                        "vehicle_make": f"{lead['car']} {lead['model']}".strip(),
                        "vehicle_location": lead["location"]
                    }
                }
            },
            timeout=15
        )

        if resp.status_code == 200:
            tg_send(f"✅ Звонок инициирован!\n👤 {lead['name']}\n📱 {lead['phone']}")
            pending_calls.pop(lead_id, None)
        else:
            tg_send(f"❌ Ошибка ElevenLabs: {resp.status_code}\n{resp.text}")

    elif cb_data.startswith("done_"):
        lead_id = cb_data.replace("done_", "")
        pending_calls.pop(lead_id, None)
        tg_send("✅ Лид отмечен как обработан.")

    return jsonify({"status": "ok"}), 200


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "Argyn Auto Lead Bot is running"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
