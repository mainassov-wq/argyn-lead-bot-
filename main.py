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
TWILIO_SID = os.environ.get("TWILIO_SID", "")
TWILIO_TOKEN = os.environ.get("TWILIO_TOKEN", "")
TWILIO_FROM = os.environ.get("TWILIO_FROM", "+16474933481")
STRIPE_LINK = os.environ.get("STRIPE_LINK", "https://buy.stripe.com/00w5kwcXQ644cn78q0fMA00")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
GROUP_ID = os.environ.get("GROUP_ID", "-1003506681231")
pending_calls = {}
phone_to_lead = {}


def build_status_message(lead):
    name = lead["name"]
    car = f"{lead['car']} {lead.get('model', '')}".strip()
    location = lead.get("location", "")
    phone = lead["phone"]
    stage = lead.get("stage", 0)
    contact = lead.get("contact_method", "")
    circle = "🟢" if stage == 3 else "🟡" if stage >= 1 else "🔵"

    if contact == "call":
        s1 = "✅" if stage >= 1 else "⏳" if stage == 0 else "⬜"
        s2 = "✅" if stage >= 2 else "⏳" if stage == 1 else "⬜"
        s3 = "✅" if stage >= 3 else "⏳" if stage == 2 else "⬜"
        return (
            f"{circle} *{name}* | {car}\n"
            f"📱 {phone} | 📍 {location}\n"
            f"📞 Метод: Звонок\n\n"
            f"1️⃣ Звонок — {s1}\n"
            f"2️⃣ SMS ссылка — {s2}\n"
            f"3️⃣ Оплата — {s3}"
        )
    else:
        s1 = "✅" if stage >= 1 else "⏳" if stage == 0 else "⬜"
        s2 = "✅" if stage >= 2 else "⏳" if stage == 1 else "⬜"
        s3 = "✅" if stage >= 3 else "⏳" if stage == 2 else "⬜"
        # Extra details collected during SMS
        year = lead.get("year", "—")
        address = lead.get("address", "—")
        timing = lead.get("timing", "—")
        present = lead.get("present", "—")
        return (
            f"{circle} *{name}* | {car}\n"
            f"📱 {phone} | 📍 {location}\n"
            f"💬 Метод: SMS\n\n"
            f"1️⃣ Переписка — {s1}\n"
            f"2️⃣ Ссылка отправлена — {s2}\n"
            f"3️⃣ Оплачено — {s3}\n\n"
            f"📋 *Детали:*\n"
            f"🚗 Год: {year}\n"
            f"📍 Адрес: {address}\n"
            f"📅 Когда: {timing}\n"
            f"👤 Присутствует: {present}"
        )


def tg_send(text, reply_markup=None):
    payload = {"chat_id": ADMIN_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        r = requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=10)
        return r.json().get("result", {}).get("message_id")
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


def create_topic(name):
    try:
        r = requests.post(f"{TELEGRAM_API}/createForumTopic", json={
            "chat_id": GROUP_ID,
            "name": name[:128]
        }, timeout=10)
        result = r.json()
        logger.info(f"Create topic response: {result}")
        thread_id = result.get("result", {}).get("message_thread_id")
        return thread_id
    except Exception as e:
        logger.error(f"Create topic error: {e}")
        return None

def tg_send_topic(thread_id, text, reply_markup=None):
    payload = {
        "chat_id": GROUP_ID,
        "message_thread_id": thread_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        r = requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=10)
        return r.json().get("result", {}).get("message_id")
    except Exception as e:
        logger.error(f"Telegram topic send error: {e}")
        return None

def send_sms(to_number, message):
    try:
        r = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json",
            auth=(TWILIO_SID, TWILIO_TOKEN),
            data={"From": TWILIO_FROM, "To": to_number, "Body": message},
            timeout=10
        )
        result = r.json()
        logger.info(f"SMS sent: {result.get('sid')} to {to_number}")
        return result.get("sid")
    except Exception as e:
        logger.error(f"SMS error: {e}")
        return None


# ============ SMS CONVERSATION ============
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
sms_conversations = {}  # phone -> list of messages

SMS_SYSTEM_PROMPT = """You are Alex, a booking coordinator for ARGYN AUTO in Toronto. You are NOT an AI — you're a real person texting from the office.

You just received an inspection request from this customer on argynauto.ca. You already have their name, vehicle, and location from the form — use this info naturally.

STYLE RULES (critical):
- This is SMS — keep every message SHORT (2-4 sentences MAX)
- Sound casual and human: use "yeah", "so", "honestly", "for sure", "nice"
- NEVER send walls of text
- Ask ONE question per message — never stack multiple questions
- Use natural reactions: "Oh nice!", "Got it!", "Yeah totally"
- Occasional typos or casual punctuation are fine
- Never sound like a bot or a script

CONVERSATION FLOW:
1. Opening — friendly, reference their vehicle from the form
2. Confirm model + year (you already have make from form)
3. Confirm location (dealer or private seller?)
4. Ask timing — when do they want the inspection?
5. Mention price: "$199 flat, no hidden fees"
6. Ask: "Want me to send the payment link by text?"
7. When they confirm → end your message with: SEND_PAYMENT_LINK

OPENING MESSAGE (use this for first contact):
"Hey [name]! This is Alex from Argyn Auto — saw your inspection request just come through for the [vehicle] 👍 Quick question — what's the year and model?"

KEY INFO:
- Price: $199 CAD flat rate, no hidden fees
- We come to the car (dealer or private seller)
- Report delivered within 24h — photos, repair costs, everything
- Coverage: Toronto, North York, Scarborough, Etobicoke, Mississauga, Brampton, Vaughan, Markham, Richmond Hill
- Same day inspections available
- Payment link: sent when customer confirms

OBJECTION HANDLING (keep responses short!):
- "$199 too much" → "Honestly for a $15-20k car purchase it's worth it — most people use the report to negotiate the price down anyway 😄"
- "Do I need to be there?" → "Nope! We just need access to the car. If it's at a dealer we deal with them directly."
- "How do I get the report?" → "Email within 24h — photos, grades, repair costs, all of it."
- "Are you AI?" → "Ha nope, real person texting from the office 😄"
- "Can I cancel?" → "Yeah reach out to the team — info's on argynauto.ca"

RULES:
- ALWAYS mention $199 ONCE before sending the link
- NEVER send the link without customer confirming they want it
- NEVER ask more than one question per message
- NEVER confirm exact inspection time — say "team confirms after payment"
- When customer confirms they want the link → write SEND_PAYMENT_LINK at the end of your message
- If you don't know something → "Good question — let me have the team follow up!"
- Only discuss Argyn Auto inspections — stay on topic"""


def get_ai_response(phone, customer_message, lead_info=None):
    history = sms_conversations.get(phone, [])
    
    if not history and lead_info:
        system = SMS_SYSTEM_PROMPT + f"\n\nCustomer info from form:\n- Name: {lead_info.get('name', '')}\n- Vehicle: {lead_info.get('car', '')} {lead_info.get('model', '')}\n- Location: {lead_info.get('location', '')}"
    else:
        system = SMS_SYSTEM_PROMPT
    
    history.append({"role": "user", "content": customer_message})
    
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-haiku-4-5",
                "max_tokens": 300,
                "system": system,
                "messages": history
            },
            timeout=15
        )
        result = r.json()
        ai_message = result["content"][0]["text"]
        history.append({"role": "assistant", "content": ai_message})
        sms_conversations[phone] = history[-20:]
        return ai_message
    except Exception as e:
        logger.error(f"Claude API error: {e}")
        return "Hey! Thanks for reaching out. I'll have someone from our team follow up shortly. Questions? Call (647) 594-7510"



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
        "message_id": None, "thread_id": None
    }
    pending_calls[lead_id] = lead
    phone_to_lead[phone_e164] = lead_id

    # Create topic in group
    car_short = f"{car} {model}".strip()[:30]
    topic_name = f"{name} | {car_short}"
    thread_id = create_topic(topic_name)
    lead["thread_id"] = thread_id

    # Build keyboard
    keyboard = {"inline_keyboard": []}
    if contact_method == "call":
        keyboard["inline_keyboard"].append([{"text": "📞 Позвонить через Alex", "callback_data": f"call_{lead_id}"}])
    keyboard["inline_keyboard"].append([{"text": "✅ Обработан", "callback_data": f"done_{lead_id}"}])

    # Send to group topic only
    if thread_id:
        msg_id = tg_send_topic(thread_id, build_status_message(lead), keyboard)
        lead["message_id"] = msg_id

    # If SMS — start conversation
    if contact_method == "sms" and phone_e164:
        car = f"{lead.get('car', '')} {lead.get('model', '')}".strip()
        opener = f"Hey {name}! This is Alex from Argyn Auto — saw your inspection request just come through for the {car} 👍 Quick question — what\'s the year and trim?"
        sms_conversations[phone_e164] = [{"role": "assistant", "content": opener}]
        send_sms(phone_e164, opener)
        if thread_id:
            tg_send_topic(thread_id, f"🤖 *Alex:* {opener}")

    return jsonify({"status": "ok"}), 200


@app.route("/postcall", methods=["POST"])
def post_call():
    import json
    raw = request.get_data(as_text=True)
    try:
        data = json.loads(raw) if raw else {}
    except Exception:
        data = request.get_json(force=True, silent=True) or {}
    
    inner_data = data.get("data", {})
    # phone_call находится внутри metadata
    phone_call = inner_data.get("metadata", {}).get("phone_call", {})
    external_number = phone_call.get("external_number", "")
    
    # fallback 1: dynamic_variables
    if not external_number:
        dyn = inner_data.get("conversation_initiation_client_data", {}).get("dynamic_variables", {})
        external_number = dyn.get("system__called_number", "")
    
    # fallback 2: user_id
    if not external_number:
        external_number = inner_data.get("user_id", "")
    
    logger.info(f"Post-call: external_number={external_number}")

    if not external_number:
        logger.warning("No external_number found anywhere")
        return jsonify({"status": "ok"}), 200

    logger.info(f"Post-call: sending SMS to {external_number}")

    sms_message = (
        f"Hi! Thanks for chatting with Alex from Argyn Auto 🚗\n\n"
        f"Here's your inspection booking link:\n{STRIPE_LINK}\n\n"
        f"Questions? Reply or call (647) 594-7510"
    )
    sid = send_sms(external_number, sms_message)

    lead_id = None
    for p, lid in phone_to_lead.items():
        p_digits = "".join(filter(str.isdigit, p))
        e_digits = "".join(filter(str.isdigit, external_number))
        if p_digits == e_digits or p_digits.endswith(e_digits) or e_digits.endswith(p_digits):
            lead_id = lid
            break

    if lead_id:
        lead = pending_calls.get(lead_id)
        if lead:
            lead["stage"] = 2
            keyboard = {"inline_keyboard": [[{"text": "✅ Обработан", "callback_data": f"done_{lead_id}"}]]}
            if lead["message_id"]:
                tg_edit(lead["message_id"], build_status_message(lead), keyboard)

    # Notify in lead topic if exists
    if lead_id and lead_info and lead_info.get("thread_id"):
        tid = lead_info["thread_id"]
        if sid:
            tg_send_topic(tid, f"📤 SMS со ссылкой отправлено клиенту!")
        else:
            tg_send_topic(tid, f"❌ Ошибка отправки SMS!")
    else:
        if sid:
            tg_send(f"📤 SMS отправлено клиенту {external_number}")
        else:
            tg_send(f"❌ Ошибка отправки SMS на {external_number}")

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

        thread_id = lead.get("thread_id")
        if thread_id:
            tg_send_topic(thread_id, f"⏳ Звоню {lead['name']} на {lead['phone']}...")
        else:
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
            keyboard = {"inline_keyboard": [[{"text": "✅ Обработан", "callback_data": f"done_{lead_id}"}]]}
            if lead["message_id"]:
                tg_edit(lead["message_id"], build_status_message(lead), keyboard)
            else:
                if thread_id:
                    tg_send_topic(thread_id, f"✅ Звонок инициирован!")
                else:
                    tg_send(f"✅ Звонок инициирован!\n👤 {lead['name']}\n📱 {lead['phone']}")
        else:
            if thread_id:
                tg_send_topic(thread_id, f"❌ Ошибка ElevenLabs: {resp.status_code}")
            else:
                tg_send(f"❌ Ошибка ElevenLabs: {resp.status_code}\n{resp.text}")

    elif cb_data.startswith("done_"):
        lead_id = cb_data.replace("done_", "")
        lead = pending_calls.get(lead_id)
        if lead:
            tid = lead.get("thread_id")
            phone_to_lead.pop(lead["phone"], None)
            pending_calls.pop(lead_id, None)
            if tid:
                tg_send_topic(tid, "✅ Лид обработан.")
            else:
                tg_send("✅ Лид отмечен как обработан.")
        else:
            tg_send("✅ Лид отмечен как обработан.")

    return jsonify({"status": "ok"}), 200


@app.route("/stripe-webhook", methods=["POST"])
def stripe_webhook():
    payload = request.get_json(force=True) or {}
    event_type = payload.get("type", "")
    if event_type not in ("payment_intent.succeeded", "checkout.session.completed"):
        return jsonify({"status": "ignored"}), 200

    obj = payload.get("data", {}).get("object", {})
    metadata = obj.get("metadata", {})
    phone = metadata.get("phone") or metadata.get("phone_number") or ""
    customer_name = metadata.get("customer_name") or metadata.get("name") or ""

    lead_id = phone_to_lead.get(phone)
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


@app.route("/sms-sent", methods=["POST"])
def sms_sent():
    data = request.json or {}
    phone = data.get("phone_number", "")
    phone_digits = "".join(filter(str.isdigit, phone))
    lead_id = None
    for p, lid in phone_to_lead.items():
        p_digits = "".join(filter(str.isdigit, p))
        if p_digits == phone_digits or p_digits.endswith(phone_digits) or phone_digits.endswith(p_digits):
            lead_id = lid
            break
    if lead_id:
        lead = pending_calls.get(lead_id)
        if lead:
            lead["stage"] = 2
            if lead["message_id"]:
                keyboard = {"inline_keyboard": [[{"text": "✅ Обработан", "callback_data": f"done_{lead_id}"}]]}
                tg_edit(lead["message_id"], build_status_message(lead), keyboard)
    return jsonify({"status": "ok"}), 200


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "Argyn Auto Lead Bot is running"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)



@app.route("/sms-incoming", methods=["POST"])
def sms_incoming():
    """Twilio sends incoming SMS here"""
    from_number = request.form.get("From", "")
    body = request.form.get("Body", "").strip()
    logger.info(f"Incoming SMS from {from_number}: {body}")

    # Find lead info
    lead_id = phone_to_lead.get(from_number)
    lead_info = pending_calls.get(lead_id) if lead_id else None

    # Get AI response
    ai_response = get_ai_response(from_number, body, lead_info)

    # Check if we should send payment link
    send_link = "SEND_PAYMENT_LINK" in ai_response
    ai_response = ai_response.replace("SEND_PAYMENT_LINK", "").strip()

    # Forward to topic
    thread_id = lead_info.get("thread_id") if lead_info else None
    if thread_id:
        tg_send_topic(thread_id, f"👤 *Клиент:* {body}")
        tg_send_topic(thread_id, f"🤖 *Alex:* {ai_response}")

    # Send SMS response
    send_sms(from_number, ai_response)

    # Send payment link if triggered
    if send_link:
        send_sms(from_number, f"Here's your secure booking link 👇\n{STRIPE_LINK}")
        if thread_id:
            tg_send_topic(thread_id, f"💳 Ссылка на оплату отправлена клиенту!")
        if lead_id and lead_info:
            lead_info["stage"] = 2
            if lead_info.get("message_id"):
                keyboard = {"inline_keyboard": [[{"text": "✅ Обработан", "callback_data": f"done_{lead_id}"}]]}
                tg_edit(lead_info["message_id"], build_status_message(lead_info), keyboard)

    return "", 204
