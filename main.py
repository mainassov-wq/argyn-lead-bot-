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
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# lead_id -> { name, phone, car, model, location, contact_method, message_id, stage }
pending_calls = {}
# phone_e164 -> lead_id  (для поиска по номеру телефона)
phone_to_lead = {}


def build_status_message(lead):
    name = lead["name"]
    car = f"{lead['car']} {lead.get('model', '')}".strip()
    location = lead.get("location", "")
    phone = lead["phone"]
    stage = lead.get("stage", 0)

    # Этапы
    s1 = "✅" if stage >= 1 else "⏳" if stage == 0 else "⬜"
    s2 = "✅" if stage >= 2 else "⏳" if stage == 1 else "⬜"
    s3 = "✅" if stage >= 3 else "⏳" if stage == 2 else "⬜"

    # Цвет заголовка
    if stage == 3:
        circle = "🟢"
    elif stage >= 1:
        circle = "🟡"
    else:
        circle = "🔵"

    return (
        f"{circle} *{name}* | {car}\n"
        f"📱 {phone} | 📍 {location}\n\n"
        f"1️⃣ Звонок — {s1}\n"
        f"2️⃣ SMS — {s2}\n"
        f"3️⃣ Оплата — {s3}"
    )


def tg_send(text, reply_markup=None):
    payload = {"chat_id": ADMIN_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        r = requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=10)
        data = r.json()
        return data.get("result", {}).get("message_id")
    except Exception as e:
        logger.error(f"Telegram send error: {e}")
        return None


def tg_edit(message_id, text, reply_markup=None):
    payload = {"chat_id": ADMIN_CHAT_ID, "message_id": message_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(f"{TELEGRAM_API}/editMessageText", json=payload, timeout=10)
    except Exception as e:
        logger.error(f"Telegram edit error: {e}")


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

    lead = {
        "name": name, "phone": phone_e164, "car": car,
        "model": model, "location": location,
        "contact_method": contact_method, "stage": 0,
        "message_id": None
    }
    pending_calls[lead_id] = lead
    phone_to_lead[phone_e164] = lead_id

    contact_emoji = "📞" if contact_method == "call" else "💬" if "sms" in contact_method else "💚"

    keyboard = {"inline_keyboard": []}
    if contact_method == "call":
        keyboard["inline_keyboard"].append([{"text": "📞 Позвонить через Alex", "callback_data": f"call_{lead_id}"}])
    keyboard["inline_keyboard"].append([{"text": "✅ Обработан", "callback_data": f"done_{lead_id}"}])

    # Отправляем сообщение с начальным статусом
    status_text = build_status_message(lead)
    msg_id = tg_send(status_text, keyboard)
    lead["message_id"] = msg_id

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
            lead["stage"] = 1
            if lead["message_id"]:
                keyboard = {"inline_keyboard": [[{"text": "✅ Обработан", "callback_data": f"done_{lead_id}"}]]}
                tg_edit(lead["message_id"], build_status_message(lead), keyboard)
            else:
                tg_send(f"✅ Звонок инициирован!\n👤 {lead['name']}\n📱 {lead['phone']}")
        else:
            tg_send(f"❌ Ошибка ElevenLabs: {resp.status_code}\n{resp.text}")

    elif cb_data.startswith("done_"):
        lead_id = cb_data.replace("done_", "")
        lead = pending_calls.get(lead_id)
        if lead:
            phone_to_lead.pop(lead["phone"], None)
            pending_calls.pop(lead_id, None)
        tg_send("✅ Лид отмечен как обработан.")

    return jsonify({"status": "ok"}), 200


@app.route("/sms-sent", methods=["POST"])
def sms_sent():
    """Zapier вызывает этот endpoint после отправки SMS"""
    data = request.json or {}
    phone = data.get("phone_number", "")
    logger.info(f"SMS sent received: phone={phone}, known phones={list(phone_to_lead.keys())}")

    # Нормализуем номер — убираем всё кроме цифр для сравнения
    phone_digits = "".join(filter(str.isdigit, phone))

    lead_id = None
    for p, lid in phone_to_lead.items():
        p_digits = "".join(filter(str.isdigit, p))
        if p_digits == phone_digits or p_digits.endswith(phone_digits) or phone_digits.endswith(p_digits):
            lead_id = lid
            break

    logger.info(f"SMS sent: matched lead_id={lead_id}")

    if lead_id:
        lead = pending_calls.get(lead_id)
        if lead:
            lead["stage"] = 2
            if lead["message_id"]:
                keyboard = {"inline_keyboard": [[{"text": "✅ Обработан", "callback_data": f"done_{lead_id}"}]]}
                tg_edit(lead["message_id"], build_status_message(lead), keyboard)
    else:
        tg_send(f"📤 SMS отправлено на {phone}")

    return jsonify({"status": "ok"}), 200


@app.route("/stripe-webhook", methods=["POST"])
def stripe_webhook():
    """Stripe вызывает этот endpoint после успешной оплаты"""
    payload = request.get_json(force=True) or {}

    event_type = payload.get("type", "")
    if event_type not in ("payment_intent.succeeded", "checkout.session.completed"):
        return jsonify({"status": "ignored"}), 200

    # Достаём телефон из metadata
    obj = payload.get("data", {}).get("object", {})
    metadata = obj.get("metadata", {})
    phone = metadata.get("phone") or metadata.get("phone_number") or ""
    customer_name = metadata.get("customer_name") or metadata.get("name") or ""

    lead_id = phone_to_lead.get(phone)
    if not lead_id and phone:
        for p, lid in phone_to_lead.items():
            if p.replace("+", "") == phone.replace("+", ""):
                lead_id = lid
                break

    if lead_id:
        lead = pending_calls.get(lead_id)
        if lead:
            lead["stage"] = 3
            if lead["message_id"]:
                tg_edit(lead["message_id"], build_status_message(lead))
    else:
        amount = obj.get("amount_total") or obj.get("amount", 0)
        amount_str = f"${amount / 100:.0f}" if amount else "$199"
        tg_send(f"💳 *Оплата получена!*\n👤 {customer_name}\n📱 {phone}\n💰 {amount_str} CAD")

    return jsonify({"status": "ok"}), 200


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "Argyn Auto Lead Bot is running"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
