import os
import logging
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8711518982:AAEshDeMsvh9-lTPYa9LgNtOC_kifTJPBbs")
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "576402316"))
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "030e5675b8947cc061f16c79e718ee3c6375ce89f33c0b7ffb824d2f85b5f721")
AGENT_ID = os.environ.get("AGENT_ID", "agent_3201kks4x6b4echvgxrdght0xn2q")
AGENT_PHONE_NUMBER_ID = os.environ.get("AGENT_PHONE_NUMBER_ID", "phnum_8301kkqsspqdedk92txj26vhgw4v")

bot = Bot(token=BOT_TOKEN)
pending_calls = {}

@app.route("/lead", methods=["POST", "OPTIONS"])
def receive_lead():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    data = request.json or request.form.to_dict()
    logger.info(f"New lead received: {data}")

    name = data.get("full_name") or data.get("name", "Unknown")
    phone = data.get("phone", "")
    car = data.get("car_brand") or data.get("vehicle_make", "")
    location = data.get("vehicle_location") or data.get("location", "")
    contact_method = data.get("contact_method", "").lower()
    model = data.get("model", "")

    phone_clean = "".join(filter(str.isdigit, phone))
    if not phone_clean.startswith("1"):
        phone_clean = "1" + phone_clean
    phone_e164 = "+" + phone_clean

    lead_id = phone_clean

    pending_calls[lead_id] = {
        "name": name,
        "phone": phone_e164,
        "car": car,
        "model": model,
        "location": location,
        "contact_method": contact_method
    }

    contact_emoji = "📞" if contact_method == "call" else "💬" if "sms" in contact_method else "💚"

    message = (
        f"🔔 *Новый лид!*\n\n"
        f"👤 *Имя:* {name}\n"
        f"📱 *Телефон:* {phone_e164}\n"
        f"🚗 *Машина:* {car} {model}\n"
        f"📍 *Локация:* {location}\n"
        f"{contact_emoji} *Метод связи:* {contact_method}\n"
    )

    keyboard = []
    if contact_method == "call":
        keyboard.append([InlineKeyboardButton("📞 Позвонить через Alex (ElevenLabs)", callback_data=f"call_{lead_id}")])
    keyboard.append([InlineKeyboardButton("✅ Отметить как обработан", callback_data=f"done_{lead_id}")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    import asyncio
    asyncio.run(send_message(message, reply_markup))

    return jsonify({"status": "ok"}), 200


async def send_message(text, reply_markup=None):
    await bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=text,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    import asyncio
    update_data = request.json
    update = Update.de_json(update_data, bot)

    if update.callback_query:
        asyncio.run(handle_callback(update.callback_query))

    return jsonify({"status": "ok"}), 200


async def handle_callback(callback_query):
    data = callback_query.data

    if data.startswith("call_"):
        lead_id = data.replace("call_", "")
        lead = pending_calls.get(lead_id)

        if not lead:
            await bot.send_message(chat_id=ADMIN_CHAT_ID, text="❌ Лид не найден или уже обработан.")
            return

        await bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"⏳ Инициирую звонок для {lead['name']}...")

        response = requests.post(
            "https://api.elevenlabs.io/v1/convai/twilio/outbound-call",
            headers={
                "xi-api-key": ELEVENLABS_API_KEY,
                "Content-Type": "application/json"
            },
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
            }
        )

        if response.status_code == 200:
            await bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"✅ Звонок инициирован!\n👤 {lead['name']}\n📱 {lead['phone']}"
            )
            del pending_calls[lead_id]
        else:
            await bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"❌ Ошибка звонка: {response.text}"
            )

    elif data.startswith("done_"):
        lead_id = data.replace("done_", "")
        if lead_id in pending_calls:
            del pending_calls[lead_id]
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text="✅ Лид отмечен как обработан.")

    await bot.answer_callback_query(callback_query.id)


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "Argyn Auto Lead Bot is running"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
