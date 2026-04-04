import os
import logging
import requests
import time
import random
import threading
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
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

# Argyn inspector bot (for nego payment notifications + inspector assignments)
ARGYN_BOT_TOKEN = os.environ.get("ARGYN_BOT_TOKEN", "8744558713:AAHXIYziu5k8PkpBcur4x9FokkiTmBJnFfI")
ARGYN_GROUP_ID  = os.environ.get("ARGYN_GROUP_ID", "-1003828934512")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
ARGYN_API = f"https://api.telegram.org/bot{ARGYN_BOT_TOKEN}"
INSPECTOR_BOT_URL = os.environ.get("INSPECTOR_BOT_URL", "")  # URL inspector_bot.py на Railway
GROUP_ID = os.environ.get("GROUP_ID", "-1003506681231")
pending_calls = {}
phone_to_lead = {}

# ─── INSPECTORS ───────────────────────────────────────────────────────────────
# Добавляй инспекторов сюда: {telegram_id: "Имя"}
INSPECTORS = {
    8317732562: "Inspector 1",
}
# Хранит назначения: {lead_id: inspector_id}
assigned_inspectors = {}


def notify_inspector_bot(lead_id, inspector_id, lead):
    """Отправить назначение в inspector_bot.py."""
    if not INSPECTOR_BOT_URL:
        logger.error("INSPECTOR_BOT_URL not set")
        return False
    car = f"{lead.get('car', '')} {lead.get('model', '')}".strip()
    try:
        r = requests.post(f"{INSPECTOR_BOT_URL}/assign", json={
            "lead_id": lead_id,
            "inspector_id": inspector_id,
            "inspector_name": INSPECTORS.get(inspector_id, "Inspector"),
            "client_name": lead.get("name", "—"),
            "car": car,
            "year": lead.get("year", "—"),
            "address": lead.get("address", "—"),
            "dealer": lead.get("dealer", "—"),
            "timing": lead.get("timing", "—"),
            "client_phone": lead.get("phone", "—"),
        }, timeout=10)
        return r.status_code == 200
    except Exception as e:
        logger.error(f"Inspector bot notify error: {e}")
        return False


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
        year = lead.get("year", "—")
        address = lead.get("address", "—")
        timing = lead.get("timing", "—")
        present = lead.get("present", "—")
        dealer = lead.get("dealer", "—")
        return (
            f"{circle} *{name}* | {car}\n"
            f"📱 {phone} | 📍 {location}\n"
            f"📞 Метод: Звонок\n\n"
            f"1️⃣ Звонок — {s1}\n"
            f"2️⃣ SMS ссылка — {s2}\n"
            f"3️⃣ Оплата — {s3}\n\n"
            f"📋 *Детали:*\n"
            f"🚗 Год: {year}\n"
            f"📍 Адрес: {address}\n"
            f"🏪 Dealer/Private: {dealer}\n"
            f"📅 Когда: {timing}\n"
            f"👤 Присутствует: {present}"
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


def tg_edit_topic(message_id, text, reply_markup=None):
    """Edit a message inside a group topic (uses GROUP_ID)"""
    payload = {"chat_id": GROUP_ID, "message_id": message_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        r = requests.post(f"{TELEGRAM_API}/editMessageText", json=payload, timeout=10)
        result = r.json()
        if not result.get("ok"):
            logger.error(f"tg_edit_topic failed: {result}")
    except Exception as e:
        logger.error(f"Telegram edit topic error: {e}")


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
paused_conversations = set()  # phones where bot is paused
unknown_number_asked = set()  # phones we asked "do you want inspection?"

SMS_SYSTEM_PROMPT = """You are Alex, a booking coordinator for ARGYN AUTO in Toronto. You are NOT an AI — you're a real person texting from the office. You know cars well and speak like someone who works around them every day.

You just received an inspection request from this customer on argynauto.ca. You already have their name, vehicle, and location from the form — use this info naturally.

STYLE RULES (critical):
- This is SMS — keep every message SHORT (2-4 sentences MAX)
- Sound casual and human: use "yeah", "so", "honestly", "for sure", "nice"
- NEVER send walls of text
- Ask ONE question per message — never stack multiple questions
- Use natural reactions: "Oh nice!", "Got it!", "Yeah totally"
- Occasional typos or casual punctuation are fine
- Never sound like a bot or a script
- Show you know the car they're asking about — mention common issues, known problems, or what to look out for on that specific model

CONVERSATION FLOW — follow this EXACT ORDER, one question per message:
1. Opening — friendly, reference their vehicle from the form
2. Ask: year and trim of the vehicle
3. Ask: dealer or private seller?
4. Ask: exact address or dealership name where the car is
5. Ask: when do they want the inspection? (today, tomorrow, specific day)
6. Ask: "And would you like to be there during the inspection, or are you okay with us handling it directly with the seller/dealer?"
7. *** PRE-PAYMENT CHECK — MANDATORY, NEVER SKIP ***
   Ask: "Before I send you the link — any questions about how the inspection works? 😊"
   - If they have questions → answer them HONESTLY and SHORT, then go to step 8
   - If no questions → go to step 8
8. Price + payment in ONE message:
   "It's $199 flat, no hidden fees — full report with photos and repair costs within 24-48 hours. Want me to send the payment link to this number?"
9. When they confirm → SEND_PAYMENT_LINK at end:
   "Perfect! Sending it over now 👍 SEND_PAYMENT_LINK"

*** CRITICAL: NEVER skip step 7. NEVER go from step 6 directly to step 8. ***
*** ALWAYS say "24-48 hours" never just "24 hours" ***

OPENING MESSAGE (use this for first contact):
"Hey [name]! This is Alex from Argyn Auto — saw your inspection request for the [vehicle] 👍 Quick question — what's the year and trim?"

========= WHAT WE ACTUALLY DO (memorize this — NEVER make up services we don't offer) =========

Our inspection is a MOBILE ON-SITE inspection. We come to where the car is. Here's what we check:
- Full visual exterior: paint thickness readings on every panel, panel gaps, weld inspection, signs of previous repair or accident
- Engine bay: all visible fluids (oil, coolant, brake fluid, power steering), leaks, engine noise, cold start
- OBD diagnostic scan: active codes, pending codes, cleared codes history
- Brakes: pad thickness visible through wheel openings, rotor condition, brake fluid
- Suspension & steering: visual check of shocks/struts for leaks, steering play
- Undercarriage: we use portable ramps and flashlights to check rust, subframe, rocker panels, suspension mounting points from below
- Wheel arch inspection: flashlight through each arch to check inner rust and suspension components
- Tires: tread depth, DOT date, wear pattern, brand matching
- Full road test: engine under load, transmission shifts, brake feel, suspension noise, alignment
- Interior: AC, windows, electronics, seatbelts, damage
- Battery: voltage test, terminal condition, age
- Full photo documentation of everything

WE DO NOT:
- Remove wheels
- Use a shop hoist/lift (we use portable ramps for underside access)
- Perform compression tests or leak-down tests
- Disassemble any parts

========= CRITICAL HONESTY RULES — NEVER VIOLATE =========

NEVER say "we jack up the car" or "we lift it on a hoist" or "full undercarriage diagnosis" or "we check everything underneath"
NEVER claim we remove wheels to check brakes
NEVER promise services we don't provide
If you're not sure about something → "Good question — let me check with the team and get back to you!"

If asked about lifting/hoisting: "We don't use a shop lift — this is a mobile inspection. But we bring portable ramps for underside access and use flashlights to check rust, subframe, and suspension mounting points. For structure checks, we also do paint thickness, panel gaps, and weld inspection — those are the biggest giveaways for accident history."

If asked about rust: "We check the key rust areas — rocker panels, subframe, wheel arches, and suspension points. We use ramps for underside access and flashlights through the arches. In Ontario most used cars have some surface rust — what matters is where it is and how bad. We'll tell you honestly if it's normal or a problem."

If asked about brakes without removing wheels: "We can see the pad thickness and rotor condition through the wheel openings without removing them. If we spot anything that needs a closer look, we'll flag it in the report."

If asked about structural checks: "The structure of the car can be assessed without it being in the air — welds, panel gaps, and paint thickness measurements are all giveaways if a car has been in an accident. Lifting is more for rust check, which we handle with portable ramps."

========= SELLING THE VALUE (use naturally when relevant) =========

- "Our job is to save you from buying the wrong car — we find the problems before you pay"
- "Most clients use the report to negotiate the price down — usually saves way more than the $199"
- "We're 100% independent — we work for you, not the seller"
- "If it's at a dealer, honestly dealers check the car on the lift for safety but they don't look hard at the rest. We focus on everything the seller doesn't want you to see"
- For expensive/rare cars: "Definitely worth inspecting — at that price point you want to make sure there's no hidden damage or surprise repairs"
- For older cars: "At that age/mileage there's always stuff to look for — we'll tell you exactly what to expect"

KEY INFO:
- Price: $199 CAD flat rate, no hidden fees (includes HST)
- We come to the car (dealer or private seller)
- Report delivered within 24-48h — photos, repair costs, AI market analysis, negotiation guidance
- Coverage: Toronto, North York, Scarborough, Etobicoke, Mississauga, Brampton, Vaughan, Markham, Richmond Hill, Thornhill, Oakville, Burlington
- Same day or next day inspections available
- Payment via secure online link (Stripe) or e-transfer to support@argynauto.ca

OBJECTION HANDLING (keep responses short!):
- "$199 too much" → "Honestly for a $15-20k car purchase it's worth it — most people use the report to negotiate the price down way more than $199 😄"
- "$199 + HST?" → "Nope, $199 flat — that's it, no extra fees"
- "Do I need to be there?" → "Nope! We just need access to the car. If it's at a dealer we deal with them directly."
- "How do I get the report?" → "You'll get a link to your full report online — photos, grades, repair costs, negotiation notes, everything. Usually within 24 hours."
- "Are you AI?" → "Ha nope, real person here 😄"
- "Can I cancel?" → "Yeah reach out to the team — info's on argynauto.ca"
- "Car got sold" / "Car is no longer available" → "No worries at all! Your inspection is transferable — just send us the new car details and we'll book it in, no extra charge 👍"
- "What if car sells before inspection?" → "If that happens, no stress — we transfer your booking to another car for free. You don't lose anything."
- "Can I get a refund?" → "If the car sells before we inspect, we transfer to another car at no cost. For anything else, reach out to the team and they'll sort it out."
- "e-transfer?" → "Yeah we accept e-transfer! Send $199 to support@argynauto.ca — once sent, screenshot the confirmation and text it back here 👍"
- "Do you check underneath?" → "Yeah we bring portable ramps for underside access + flashlights through the arches. We check rust, subframe, suspension mounts — all the key areas."
- "Do you remove wheels?" → "We don't remove them, but we can see pad thickness and rotor condition through the openings. If something needs a closer look we flag it."
- "Is it like a safety inspection?" → "It's more thorough than a safety — we check for rust, accident history, mechanical issues, and give you repair cost estimates. A safety just tells you pass/fail."

RULES:
- ALWAYS mention $199 ONCE before sending the link
- NEVER send the link without customer confirming they want it
- NEVER ask more than one question per message
- NEVER confirm exact inspection time — say "team confirms after payment"
- When customer confirms they want the link → write SEND_PAYMENT_LINK at the end of your message
- If you don't know something → "Good question — let me check with the team and get back to you!"
- Only discuss Argyn Auto inspections — stay on topic
- NEVER fabricate inspection capabilities — stick to what's listed above"""


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




def _handle_inbound_postcall(inner_data, caller_phone, analysis):
    """Обрабатывает входящий звонок — создаёт топик в Telegram + SMS если нужно."""
    from datetime import datetime as _dt
    conversation_id = inner_data.get("conversation_id", "n/a")
    metadata = inner_data.get("metadata", {})
    duration = metadata.get("call_duration_secs", 0)
    start_ts = metadata.get("start_time_unix_secs", 0)
    start_time = _dt.utcfromtimestamp(start_ts).strftime("%d.%m.%Y %H:%M UTC") if start_ts else "n/a"
    duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "0:00"

    summary = analysis.get("transcript_summary", "Нет саммари")
    call_success = analysis.get("call_successful", "unknown")

    # Collected data
    dc = analysis.get("data_collection_results", {})
    car_info = (dc.get("vehicle_make_model_year") or {}).get("value") or "—"
    location = (dc.get("inspection_address") or {}).get("value") or "—"
    timing = (dc.get("preferred_inspection_date_time") or {}).get("value") or "—"
    payment_sent = (dc.get("payment_link_sent_confirmation") or {}).get("value") or False

    # Transcript preview — fix None messages
    transcript = inner_data.get("transcript", [])
    preview = ""
    for turn in transcript[-6:]:
        role = "🤖" if turn.get("role") == "agent" else "👤"
        msg = (turn.get("message") or "")[:120]
        if not msg:
            continue
        preview += f"{role} {msg}\n"

    result_icon = "✅" if call_success == "success" else "❌"
    pay_icon = "✅ Отправлена" if payment_sent else "❌ Не отправлена"

    card = (
        f"📞 *ВХОДЯЩИЙ ЗВОНОК (Google)*\n"
        f"{'━' * 28}\n"
        f"📱 Номер: `{caller_phone}`\n"
        f"🕐 Время: {start_time}\n"
        f"⏱ Длительность: {duration_str}\n"
        f"{result_icon} Результат: {call_success}\n\n"
        f"🚗 Авто: {car_info}\n"
        f"📍 Локация: {location}\n"
        f"📅 Когда: {timing}\n"
        f"💳 Ссылка: {pay_icon}\n\n"
        f"💬 *Саммари:*\n{summary[:400]}\n\n"
        f"📝 *Превью:*\n{preview}"
        f"\n🆔 `{conversation_id}`"
    )

    # Создаём топик для inbound звонка
    topic_name = f"📞 {caller_phone[-10:]} | {car_info[:25]}"
    thread_id = create_topic(topic_name)

    if thread_id:
        tg_send_topic(thread_id, card)
        logger.info(f"[INBOUND] Topic created and card sent for {caller_phone}")
    else:
        # Fallback — в General
        try:
            requests.post(f"{TELEGRAM_API}/sendMessage", json={
                "chat_id": GROUP_ID,
                "text": card,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            }, timeout=10)
        except Exception as e:
            logger.error(f"[INBOUND] Telegram fallback error: {e}")

    # ── Регистрируем лид в памяти чтобы Stripe webhook нашёл топик ──
    phone_digits = "".join(filter(str.isdigit, caller_phone))
    lead_id = f"in{phone_digits}"
    inbound_lead = {
        "name": car_info,
        "phone": caller_phone,
        "car": car_info,
        "model": "",
        "location": location,
        "contact_method": "call",
        "stage": 2 if payment_sent else 1,
        "message_id": None,
        "thread_id": thread_id,
        "year": "",
        "address": location,
        "timing": timing,
        "dealer": "—",
        "present": "—",
        "source": "inbound",
    }
    pending_calls[lead_id] = inbound_lead
    phone_to_lead[caller_phone] = lead_id
    logger.info(f"[INBOUND] Lead registered: {lead_id} thread={thread_id}")

    # ── SMS с ссылкой если агент сказал что отправил но реально нет ──
    if payment_sent:
        pay_url = f"{STRIPE_LINK}?client_reference_id={lead_id}"
        sms = (
            f"Hi! Thanks for calling Argyn Auto 🚗\n\n"
            f"Here's your inspection booking link:\n{pay_url}\n\n"
            f"Questions? Call (647) 594-7510"
        )
        sid = send_sms(caller_phone, sms)
        if thread_id:
            if sid:
                tg_send_topic(thread_id, "📤 SMS со ссылкой отправлено клиенту!")
            else:
                tg_send_topic(thread_id, "❌ Ошибка отправки SMS клиенту")
        logger.info(f"[INBOUND] SMS sent to {caller_phone}: {sid}")

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
    logger.info(f"Post-call full inner_data: {json.dumps(inner_data)}")

    if not external_number:
        logger.warning("No external_number found anywhere")
        return jsonify({"status": "ok"}), 200

    # ── Определяем направление: outbound = мы звонили, inbound = клиент звонил сам
    dyn_vars = inner_data.get("conversation_initiation_client_data", {}).get("dynamic_variables", {})
    is_outbound = bool(dyn_vars.get("customer_name"))
    logger.info(f"Post-call: direction={'outbound' if is_outbound else 'inbound'} number={external_number}")

    analysis = inner_data.get("analysis", {})

    # ── INBOUND: входящий звонок с Google — шлём карточку в Telegram ──
    if not is_outbound:
        _handle_inbound_postcall(inner_data, external_number, analysis)
        return jsonify({"status": "ok"}), 200
    # ──────────────────────────────────────────────────────────────────

    # ── OUTBOUND: проверяем предложил ли агент ссылку на оплату ──────
    criteria_results = analysis.get("evaluation_criteria_results", {})
    payment_offered = criteria_results.get("payment_link_offered", {}).get("result")
    logger.info(f"Post-call: payment_link_offered={payment_offered}")

    if payment_offered != "success":
        logger.info("Агент не предложил ссылку на оплату, SMS не отправляем")
        return jsonify({"status": "ok"}), 200
    # ─────────────────────────────────────────────────────────────────

    logger.info(f"Post-call: отправляем SMS на {external_number}")

    # Find lead by phone FIRST so we can build personalized pay link
    phone_digits = "".join(filter(str.isdigit, external_number))
    lead_id = None
    for p, lid in phone_to_lead.items():
        p_digits = "".join(filter(str.isdigit, p))
        if p_digits == phone_digits or p_digits.endswith(phone_digits) or phone_digits.endswith(p_digits):
            lead_id = lid
            break
    logger.info(f"Post-call: matched lead_id={lead_id} for {external_number}")
    lead = pending_calls.get(lead_id) if lead_id else None

    # Заполняем карточку лида данными из ElevenLabs data_collection_results
    if lead:
        dc = analysis.get("data_collection_results", {})

        vehicle_year = dc.get("vehicle_year", {}).get("value")
        if vehicle_year:
            lead["year"] = str(vehicle_year)

        vehicle_make_model = dc.get("vehicle_make_model", {}).get("value")
        if vehicle_make_model:
            lead["car"] = vehicle_make_model

        inspection_address = dc.get("inspection_address", {}).get("value")
        if inspection_address:
            lead["address"] = inspection_address

        dealer_val = dc.get("dealer_or_private", {}).get("value")
        if dealer_val:
            lead["dealer"] = dealer_val

        timing_val = dc.get("inspection_timing", {}).get("value")
        if timing_val:
            lead["timing"] = str(timing_val)

        present_val = dc.get("customer_present", {}).get("value")
        if present_val is not None:
            lead["present"] = "Да" if present_val is True else ("Нет" if present_val is False else str(present_val))

        logger.info(f"Post-call lead updated: year={vehicle_year} address={inspection_address} make_model={vehicle_make_model}")

    # Build personalized pay link with client_reference_id
    pay_url = f"{STRIPE_LINK}?client_reference_id={lead_id}" if lead_id else STRIPE_LINK
    sms_message = (
        f"Hi! Thanks for chatting with Alex from Argyn Auto 🚗\n\n"
        f"Here's your inspection booking link:\n{pay_url}\n\n"
        f"Questions? Reply or call (647) 594-7510"
    )
    sid = send_sms(external_number, sms_message)

    if lead:
        lead["stage"] = 2
        thread_id = lead.get("thread_id")
        keyboard = {"inline_keyboard": [[{"text": "✅ Обработан", "callback_data": f"done_{lead_id}"}]]}
        updated_card = build_status_message(lead)
        if thread_id:
            if lead.get("message_id"):
                tg_edit_topic(lead["message_id"], updated_card, keyboard)
            if sid:
                tg_send_topic(thread_id, f"📤 SMS со ссылкой отправлено клиенту!")
            else:
                tg_send_topic(thread_id, f"❌ Ошибка отправки SMS!")
        else:
            if sid:
                tg_send(f"📤 SMS отправлено клиенту {external_number}")
    else:
        if sid:
            tg_send(f"📤 SMS отправлено клиенту {external_number}")
        else:
            tg_send(f"❌ Ошибка отправки SMS на {external_number}")

    return jsonify({"status": "ok"}), 200


@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    data = request.json

    # Handle regular messages from admin in group topics
    message = data.get("message", {})
    if message and message.get("chat", {}).get("id") == int(GROUP_ID):
        thread_id = message.get("message_thread_id")
        text = message.get("text", "").strip()
        from_user = message.get("from", {})

        # Find lead by thread_id
        lead_for_thread = None
        lead_id_for_thread = None
        for lid, l in pending_calls.items():
            if l.get("thread_id") == thread_id:
                lead_for_thread = l
                lead_id_for_thread = lid
                break

        if lead_for_thread and text:
            phone = lead_for_thread.get("phone")

            # Handle commands
            if text.lower() == "/pause":
                paused_conversations.add(phone)
                tg_send_topic(thread_id, "⏸ Бот на паузе. Ты переписываешься вручную. /resume чтобы включить обратно.")
                return jsonify({"status": "ok"}), 200

            elif text.lower() == "/resume":
                paused_conversations.discard(phone)
                tg_send_topic(thread_id, "▶️ Бот снова активен и будет отвечать автоматически.")
                return jsonify({"status": "ok"}), 200

            elif text.lower() == "/paid":
                # Manual payment confirmation (e-transfer, cash, etc.)
                lead_for_thread["stage"] = 3
                client_phone = lead_for_thread.get("phone", "")
                car = f"{lead_for_thread.get('car', '')} {lead_for_thread.get('model', '')}".strip()

                # Update status message in topic
                updated = build_status_message(lead_for_thread)
                keyboard = {"inline_keyboard": [[{"text": "✅ Обработан", "callback_data": f"done_{lead_id_for_thread}"}]]}
                if lead_for_thread.get("message_id"):
                    tg_edit_topic(lead_for_thread["message_id"], updated, keyboard)
                tg_send_topic(thread_id, f"💳 *Оплата подтверждена вручную!* $199 CAD\n👤 {lead_for_thread.get('name', '')}\n🚗 {car}")

                # Send confirmation SMS to client
                if client_phone:
                    sms_confirmation = (
                        "Payment received! ✅\n\n"
                        "Our inspector will contact you within 2 hours to confirm the exact inspection time.\n\n"
                        "Questions? Reply to this message or call (647) 594-7510"
                    )
                    sid = send_sms(client_phone, sms_confirmation)
                    if sid:
                        tg_send_topic(thread_id, "📱 SMS с подтверждением отправлено клиенту")

                # Show inspector assignment buttons
                inspector_buttons = [[{"text": f"👨‍🔧 {name}", "callback_data": f"assign_{lead_id_for_thread}_{iid}"}]
                                      for iid, name in INSPECTORS.items()]
                if inspector_buttons:
                    inspector_keyboard = {"inline_keyboard": inspector_buttons}
                    tg_send_topic(thread_id, "👨‍🔧 *Назначь инспектора:*", inspector_keyboard)

                return jsonify({"status": "ok"}), 200

            # Forward admin message to client via SMS (only if it's not from the bot itself)
            elif not text.startswith("🤖") and not text.startswith("👤") and not text.startswith("💳") and not text.startswith("⏸") and not text.startswith("▶️") and not text.startswith("📤") and not text.startswith("🔵") and not text.startswith("🟡") and not text.startswith("🟢"):
                # Only forward if message is from a human admin (not bot)
                if not from_user.get("is_bot", False):
                    send_sms(phone, text)
                    tg_send_topic(thread_id, f"📤 Отправлено клиенту: {text}")
                    return jsonify({"status": "ok"}), 200

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
                tg_edit_topic(lead["message_id"], build_status_message(lead), keyboard)
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

    elif cb_data.startswith("assign_"):
        # Format: assign_{lead_id}_{inspector_id}
        parts = cb_data.split("_", 2)
        if len(parts) == 3:
            _, lead_id, inspector_id_str = parts
            inspector_id = int(inspector_id_str)
            lead = pending_calls.get(lead_id)
            inspector_name = INSPECTORS.get(inspector_id, "Inspector")

            if lead:
                assigned_inspectors[lead_id] = inspector_id
                thread_id = lead.get("thread_id")

                ok = notify_inspector_bot(lead_id, inspector_id, lead)

                if thread_id:
                    if ok:
                        tg_send_topic(thread_id, f"👨‍🔧 Назначен инспектор: *{inspector_name}*\nОжидаем подтверждения...")
                    else:
                        tg_send_topic(thread_id, f"❌ Ошибка отправки уведомления инспектору. Проверь INSPECTOR_BOT_URL.")
            else:
                tg_send("❌ Лид не найден.")

    elif cb_data.startswith("done_"):
        lead_id = cb_data.replace("done_", "")
        lead = pending_calls.get(lead_id)
        if lead:
            tid = lead.get("thread_id")
            phone_to_lead.pop(lead["phone"], None)
            pending_calls.pop(lead_id, None)
            assigned_inspectors.pop(lead_id, None)
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
    logger.info(f"Stripe webhook: {event_type}")
    if event_type not in ("payment_intent.succeeded", "checkout.session.completed"):
        return jsonify({"status": "ignored"}), 200

    obj = payload.get("data", {}).get("object", {})
    metadata = obj.get("metadata", {})
    phone = metadata.get("phone") or metadata.get("phone_number") or ""
    customer_name = metadata.get("customer_name") or metadata.get("name") or ""
    client_ref = obj.get("client_reference_id") or ""
    amount = obj.get("amount_total") or obj.get("amount", 0)
    amount_str = f"${amount / 100:.0f}" if amount else "$199"
    logger.info(f"Stripe payment: phone={phone} name={customer_name}")

    # Try to find lead by phone — try multiple formats
    # First try client_reference_id (most reliable — comes from our pay link)
    if client_ref and client_ref in pending_calls:
        lead_id = client_ref
    else:
        lead_id = phone_to_lead.get(phone)
    if not lead_id:
        phone_digits = "".join(filter(str.isdigit, phone))
        for p, lid in phone_to_lead.items():
            p_digits = "".join(filter(str.isdigit, p))
            if p_digits == phone_digits or p_digits.endswith(phone_digits) or phone_digits.endswith(p_digits):
                lead_id = lid
                break

    if not lead_id:
        logger.warning(f"Stripe: no lead found for phone={phone}")
        tg_send(f"💳 *Оплата получена!* {amount_str} CAD\n👤 {customer_name or 'Неизвестный'}\n📱 {phone or 'нет телефона'}\n⚠️ Лид не найден — привяжи вручную")
        return jsonify({"status": "ok"}), 200

    lead = pending_calls.get(lead_id)
    if lead:
        lead["stage"] = 3
        thread_id = lead.get("thread_id")
        client_phone = lead.get("phone", "")
        updated = build_status_message(lead)
        keyboard = {"inline_keyboard": [[{"text": "✅ Обработан", "callback_data": f"done_{lead_id}"}]]}
        if thread_id:
            if lead.get("message_id"):
                tg_edit_topic(lead["message_id"], updated, keyboard)
            tg_send_topic(thread_id, f"💳 *Оплата получена!* {amount_str} CAD")
        else:
            tg_send(f"💳 *Оплата получена!*\n👤 {customer_name}\n📱 {phone}\n💰 {amount_str} CAD")

        # Автоматический SMS клиенту после оплаты
        if client_phone:
            sms_confirmation = (
                "Payment received! ✅\n\n"
                "Our inspector will contact you within 2 hours to confirm the exact inspection time.\n\n"
                "Questions? Reply to this message or call (647) 594-7510"
            )
            sid = send_sms(client_phone, sms_confirmation)
            if sid:
                logger.info(f"Confirmation SMS sent to {client_phone}")
                if thread_id:
                    tg_send_topic(thread_id, "📱 SMS с подтверждением отправлено клиенту")
            else:
                logger.error(f"Failed to send confirmation SMS to {client_phone}")

        # Кнопка назначить инспектора
        if thread_id:
            inspector_buttons = [[{"text": f"👨‍🔧 {name}", "callback_data": f"assign_{lead_id}_{iid}"}]
                                  for iid, name in INSPECTORS.items()]
            inspector_keyboard = {"inline_keyboard": inspector_buttons}
            tg_send_topic(thread_id, "👨‍🔧 *Назначь инспектора:*", inspector_keyboard)

    return jsonify({"status": "ok"}), 200


@app.route("/stripe-nego", methods=["POST"])
def stripe_nego_webhook():
    """Handle Stripe payment for Negotiation Strategy — unlocks nego in Supabase."""
    payload = request.get_json(force=True) or {}
    event_type = payload.get("type", "")
    logger.info(f"Stripe nego webhook: {event_type}")

    if event_type != "checkout.session.completed":
        return jsonify({"status": "ignored"}), 200

    obj = payload.get("data", {}).get("object", {})
    report_id = obj.get("client_reference_id", "")
    amount = obj.get("amount_total", 0)
    amount_str = f"${amount / 100:.0f}" if amount else "$89"
    customer_email = (obj.get("customer_details") or {}).get("email", "")

    logger.info(f"Nego payment: report_id={report_id} amount={amount_str}")

    if not report_id:
        logger.warning("Nego webhook: no client_reference_id")
        tg_send(f"💰 *Nego оплата!* {amount_str} CAD\n⚠️ report_id не найден — привяжи вручную")
        return jsonify({"status": "ok"}), 200

    # Unlock in Supabase
    unlocked = False
    ymm = ""
    client_name = ""
    thread_id = None
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            # Get report info first
            r = requests.get(
                f"{SUPABASE_URL}/rest/v1/reports?id=eq.{report_id}&select=ymm,client_name,thread_id",
                headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
                timeout=10
            )
            rows = r.json()
            if rows:
                ymm = rows[0].get("ymm", "")
                client_name = rows[0].get("client_name", "")
                thread_id = rows[0].get("thread_id")

            # Unlock nego
            r2 = requests.patch(
                f"{SUPABASE_URL}/rest/v1/reports?id=eq.{report_id}",
                headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                         "Content-Type": "application/json", "Prefer": "return=minimal"},
                json={"nego_paid": True},
                timeout=10
            )
            unlocked = r2.status_code in (200, 204)
            logger.info(f"Nego unlock status: {r2.status_code}")
        except Exception as e:
            logger.error(f"Supabase nego unlock error: {e}")

    # Send notification via Argyn inspector bot to correct topic
    msg = (f"💰 *Nego Strategy продана!*\n"
           f"🚗 {ymm or '—'}\n"
           f"👤 {client_name or '—'}\n"
           f"📋 `{report_id}`\n"
           f"💵 *{amount_str} CAD*\n"
           f"📧 {customer_email or '—'}\n"
           f"{'✅ Стратегия разблокирована' if unlocked else '❌ Ошибка разблокировки'}")

    argyn_api = f"https://api.telegram.org/bot{ARGYN_BOT_TOKEN}" if ARGYN_BOT_TOKEN else TELEGRAM_API
    argyn_group = ARGYN_GROUP_ID if ARGYN_GROUP_ID else GROUP_ID

    if thread_id and argyn_group:
        try:
            requests.post(f"{argyn_api}/sendMessage", json={
                "chat_id": int(argyn_group),
                "message_thread_id": int(thread_id),
                "text": msg,
                "parse_mode": "Markdown"
            }, timeout=10)
        except Exception as e:
            logger.error(f"Argyn bot notify error: {e}")
            tg_send(msg)
    else:
        tg_send(msg)

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
                tg_edit_topic(lead["message_id"], build_status_message(lead), keyboard)
    return jsonify({"status": "ok"}), 200


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "Argyn Auto Lead Bot is running"}), 200





@app.route("/inspector-accepted", methods=["POST"])
def inspector_accepted():
    """inspector_bot.py вызывает этот endpoint когда инспектор нажал Принял."""
    data = request.json or {}
    lead_id = data.get("lead_id")
    inspector_name = data.get("inspector_name", "Inspector")

    lead = pending_calls.get(lead_id)
    if not lead:
        logger.warning(f"inspector-accepted: lead {lead_id} not found")
        return jsonify({"status": "ok"}), 200

    client_phone = lead.get("phone", "")
    thread_id = lead.get("thread_id")

    # SMS клиенту
    if client_phone:
        sms = (
            "Your inspection is confirmed! ✅\n\n"
            "Our inspector will reach out to you shortly to coordinate the details.\n\n"
            "Questions? Call (647) 594-7510"
        )
        send_sms(client_phone, sms)
        logger.info(f"Confirmation SMS sent to {client_phone}")

    # Уведомление в топик
    if thread_id:
        tg_send_topic(thread_id, f"✅ *{inspector_name}* принял заказ. SMS клиенту отправлено.")

    return jsonify({"status": "ok"}), 200


@app.route("/sms-incoming", methods=["POST"])
def sms_incoming():
    """Twilio sends incoming SMS here — returns 200 immediately, processes in background"""
    from_number = request.form.get("From", "")
    body = request.form.get("Body", "").strip()
    logger.info(f"Incoming SMS from {from_number}: {body}")

    # Respond to Twilio immediately (fix: prevents duplicate SMS on timeout)
    def process():
        _handle_incoming_sms(from_number, body)

    threading.Thread(target=process, daemon=True).start()
    return "", 204


def _handle_incoming_sms(from_number, body):
    """All SMS processing happens here in background thread"""
    try:
        lead_id = phone_to_lead.get(from_number)
        lead_info = pending_calls.get(lead_id) if lead_id else None
        thread_id = lead_info.get("thread_id") if lead_info else None

        # Unknown number — not in our system
        if not lead_info:
            body_lower = body.lower().strip()
            YES_WORDS = {"yes", "yeah", "yep", "sure", "ok", "okay", "да", "конечно", "yup", "absolutely", "y"}
            NO_WORDS = {"no", "nope", "нет", "not", "n", "nah"}

            if from_number in unknown_number_asked:
                if any(w in body_lower for w in YES_WORDS) or body_lower in YES_WORDS:
                    # Said yes — create lead and start dialogue
                    unknown_number_asked.discard(from_number)
                    phone_digits = "".join(filter(str.isdigit, from_number))
                    new_lead_id = f"sms{phone_digits[-10:]}"
                    new_lead = {"phone": from_number, "stage": 0, "source": "sms_direct"}
                    pending_calls[new_lead_id] = new_lead
                    phone_to_lead[from_number] = new_lead_id
                    opener = "Great! Let's get started. What vehicle are you looking to inspect? (year, make, model)"
                    time.sleep(random.randint(1, 3))
                    send_sms(from_number, opener)
                    sms_conversations[from_number] = [{"role": "assistant", "content": opener}]
                    return
                elif any(w in body_lower for w in NO_WORDS) or body_lower in NO_WORDS:
                    unknown_number_asked.discard(from_number)
                    time.sleep(random.randint(1, 2))
                    send_sms(from_number, "No problem! If you ever need a vehicle inspection, visit us at argynauto.ca 👍")
                    return
                else:
                    # Something meaningful — treat as yes, fall through to AI
                    unknown_number_asked.discard(from_number)
                    phone_digits = "".join(filter(str.isdigit, from_number))
                    new_lead_id = f"sms{phone_digits[-10:]}"
                    new_lead = {"phone": from_number, "stage": 0, "source": "sms_direct"}
                    pending_calls[new_lead_id] = new_lead
                    phone_to_lead[from_number] = new_lead_id
                    lead_id = new_lead_id
                    lead_info = new_lead
            else:
                # First contact — ask them
                unknown_number_asked.add(from_number)
                time.sleep(random.randint(1, 2))
                send_sms(from_number, "Hey! 👋 Are you looking to book a pre-purchase vehicle inspection?")
                return

        # If bot is paused — only forward to Telegram
        if from_number in paused_conversations:
            if thread_id:
                tg_send_topic(thread_id, f"👤 *Клиент:* {body}")
            return

        # If lead already paid — auto-reply, no AI
        if lead_info and lead_info.get("stage", 0) >= 3:
            if thread_id:
                tg_send_topic(thread_id, f"👤 *Клиент:* {body}")
            auto_reply = (
                "Thanks for reaching out! 👋 "
                "Our inspector will contact you within 2 hours to confirm the inspection time. "
                "Questions? Visit argynauto.ca"
            )
            time.sleep(random.randint(2, 4))
            send_sms(from_number, auto_reply)
            if thread_id:
                tg_send_topic(thread_id, f"🤖 *Alex (авто):* {auto_reply}")
            return

        # Forward client message to Telegram topic
        if thread_id:
            tg_send_topic(thread_id, f"👤 *Клиент:* {body}")

        # Get AI response
        ai_response = get_ai_response(from_number, body, lead_info)

        # Extract details from conversation
        if lead_info and ANTHROPIC_API_KEY:
            try:
                import json as json_mod
                history = sms_conversations.get(from_number, [])
                conv_text = "\n".join([f"{m['role']}: {m['content']}" for m in history[-12:]])
                extract_resp = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": ANTHROPIC_API_KEY,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    },
                    json={
                        "model": "claude-haiku-4-5",
                        "max_tokens": 150,
                        "system": "Extract from this SMS conversation. Return ONLY valid JSON: {year, address, timing, present}. Use null if not mentioned.",
                        "messages": [{"role": "user", "content": conv_text}]
                    },
                    timeout=8
                )
                raw = extract_resp.json()["content"][0]["text"].strip()
                clean = raw.replace("```json", "").replace("```", "").strip()
                extracted = json_mod.loads(clean)
                if extracted.get("year"): lead_info["year"] = str(extracted["year"])
                if extracted.get("address"): lead_info["address"] = extracted["address"]
                if extracted.get("timing"): lead_info["timing"] = extracted["timing"]
                if extracted.get("present"): lead_info["present"] = extracted["present"]
                if thread_id and lead_info.get("message_id"):
                    keyboard = {"inline_keyboard": [[{"text": "✅ Обработан", "callback_data": f"done_{lead_id}"}]]}
                    tg_edit_topic(lead_info["message_id"], build_status_message(lead_info), keyboard)
            except Exception as e:
                logger.error(f"Extraction error: {e}")

        # Check if we should send payment link
        send_link = "SEND_PAYMENT_LINK" in ai_response
        ai_response = ai_response.replace("SEND_PAYMENT_LINK", "").strip()

        # Forward AI response to Telegram
        if thread_id:
            tg_send_topic(thread_id, f"🤖 *Alex:* {ai_response}")

        # Human delay + send SMS
        time.sleep(random.randint(2, 4))
        send_sms(from_number, ai_response)

        # Send payment link if triggered
        if send_link:
            pay_url = f"{STRIPE_LINK}?client_reference_id={lead_id}" if lead_id else STRIPE_LINK
            send_sms(from_number, f"Here's your secure booking link 👇\n{pay_url}")
            if lead_id and lead_info:
                lead_info["stage"] = 2
                keyboard = {"inline_keyboard": [[{"text": "✅ Обработан", "callback_data": f"done_{lead_id}"}]]}
                if thread_id and lead_info.get("message_id"):
                    tg_edit_topic(lead_info["message_id"], build_status_message(lead_info), keyboard)
                    tg_send_topic(thread_id, "📤 Ссылка на оплату отправлена клиенту!")

    except Exception as e:
        logger.error(f"SMS processing error: {e}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
