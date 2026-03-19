import os
import asyncio
import aiofiles
from io import BytesIO
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, PageBreak, CondPageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle  
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Image as RLImage

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)

# ─── CONFIG ───────────────────────────────────────────────
BOT_TOKEN      = os.environ.get("BOT_TOKEN", "")
REPORT_CHAT    = os.environ.get("REPORT_CHAT_ID", "")
SUPABASE_URL   = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY   = os.environ.get("SUPABASE_KEY", "")
SITE_URL       = os.environ.get("SITE_URL", "https://argynauto.ca")

# Allowed inspector Telegram user IDs (add yours)
ALLOWED_USERS = [int(x) for x in os.environ.get("ALLOWED_USERS", "576402316").split(",") if x]

# ─── CONVERSATION STEPS ───────────────────────────────────
(
    LANG,
    VIN, PHOTO_VIN,
    YMM, ODO, PHOTO_ODO,
    TRANS, KEYS,
    DATE, LOCATION,
    # Exterior
    FRAME, RUST, PANEL_GAPS, REPAINT, WINDSHIELD, DOORS,
    # Engine
    OIL, OIL_LEAK, COOLANT_LEAK, ENGINE_NOISE, EXHAUST, COLD_START,
    # OBD
    OBD_ACTIVE, OBD_PENDING, OBD_CLEARED,
    # Transmission
    TRANS_SHIFT, TRANS_LEAK,
    # Brakes
    BRAKE_FRONT, BRAKE_REAR, BRAKE_ROTOR, BRAKE_VIB,
    # Suspension
    SUSP_NOISE, CONTROL_ARMS, SHOCKS, STEERING, WHEEL_BEARING,
    # Tires
    TIRE_FRONT, TIRE_REAR, TIRE_WEAR, TIRE_DOT, TIRE_ROT, TIRE_MATCH, SPARE,
    # Battery
    BATT_VOLT, BATT_AGE, BATT_TERM,
    # Road test
    RT_ENGINE, RT_TRANS, RT_BRAKES, RT_ALIGN, RT_SUSP, RT_LIGHTS,
    # Interior
    INT_DASH, INT_AC, INT_WIN, INT_BELTS, INT_DAMAGE,
    # Photos
    PHOTO_ENGINE, PHOTO_UNDER, PHOTO_FRONT, PHOTO_REAR, PHOTO_LEFT, PHOTO_RIGHT, PHOTO_INTERIOR,
    # Findings
    NEGO1, NEGO2, NEGO3,
    # Summary
    OVERALL, RECOMMEND, FINAL_COMMENT,
    # Client
    CLIENT_NAME,
    # Conditional
    DETAIL,
    # AI context
    ASKING_PRICE, OWNERS, SERVICE_HIST,
    # PDF theme
    PDF_THEME,
) = range(76)

# ─── LANGUAGE STRINGS ─────────────────────────────────────
T = {
    "en": {
        "welcome": "👋 Welcome to Argyn Auto Inspection Bot!\n\nI will guide you through the inspection step by step.\n\nType /cancel at any time to abort.",
        "vin": "📋 Enter the VIN number:",
        "photo_vin": "📸 Photo of the VIN plate (or type the number):",
        "ymm": "🚗 Year / Make / Model (e.g. 2019 BMW 435i):",
        "odo": "🔢 Odometer reading (exact number, km):",
        "photo_odo": "📸 Photo of the odometer (or /skip):",
        "trans": "⚙️ Transmission — Auto / Manual / CVT:",
        "keys": "🔑 Number of keys available:",
        "date": "📅 Inspection date (e.g. 2026-03-07):",
        "location": "📍 Inspection location (city/address):",
        "frame": "🏗 Frame — straight / repaired welds visible / bent:",
        "rust": "🔩 Undercarriage rust — none / surface only / structural (location?):",
        "panel_gaps": "📐 Panel gaps — even / uneven (which panels?):",
        "repaint": "🎨 Repaint — none / partial (panels?) / full respray:",
        "windshield": "🪟 Windshield — no damage / chip (size?) / crack (length?):",
        "doors": "🚪 Doors — all OK / issues (which door, what issue?):",
        "oil": "🛢 Oil — full+clean / low / dark / milky:",
        "oil_leak": "💧 Oil leaks — none / minor seep / active drip (location?):",
        "coolant_leak": "🌡 Coolant leaks — none / minor / active (location?):",
        "engine_noise": "🔊 Engine noise — quiet / tick / knock / rattle (RPM?):",
        "exhaust": "💨 Exhaust smoke — none / white / blue / black:",
        "cold_start": "❄️ Cold start — smooth / rough / hesitation / misfire:",
        "obd_active": "🔍 Active OBD codes — none / present (list codes):",
        "obd_pending": "⏳ Pending codes — none / present (list codes):",
        "obd_cleared": "🗑 Recently cleared codes — no / yes:",
        "trans_shift": "⚙️ Shifts — smooth / delayed / harsh / slipping:",
        "trans_leak": "💧 Trans fluid — clean+full / low / leak present:",
        "brake_front": "🛑 Front pads remaining — 1-3mm / 4-6mm / 7mm+:",
        "brake_rear": "🛑 Rear pads remaining — 1-3mm / 4-6mm / 7mm+:",
        "brake_rotor": "⭕ Rotors — smooth / light grooves / deep grooves / warped:",
        "brake_vib": "📳 Brake vibration — none / slight / strong:",
        "susp_noise": "🔊 Suspension noise — none / clunk / squeak (location?):",
        "control_arms": "🔧 Control arms / ball joints — tight / slight play / worn:",
        "shocks": "🚗 Shocks/struts — firm / soft / leaking:",
        "steering": "🎯 Steering — tight / slight play / excessive play:",
        "wheel_bearing": "🔄 Wheel bearings — quiet / hum (which wheel?):",
        "tire_front": "🔵 Front tread depth (mm, both sides):",
        "tire_rear": "🔵 Rear tread depth (mm, both sides):",
        "tire_wear": "📊 Wear pattern — even / inner edge / outer edge / centre:",
        "tire_dot": "📅 Tire DOT year (last 4 digits of DOT code):",
        "tire_rot": "⚠️ Tire condition — good / dry rot / sidewall cracks:",
        "tire_match": "✅ All 4 tires same brand and size — yes / no (details?):",
        "spare": "🔄 Spare — full size+inflated / compact / none:",
        "batt_volt": "⚡ Battery voltage (engine off, e.g. 12.6V):",
        "batt_age": "📅 Battery age (years, or unknown):",
        "batt_term": "🔌 Battery terminals — clean / corrosion present:",
        "rt_engine": "🏎 Engine under load — smooth / hesitation / power loss:",
        "rt_trans": "⚙️ Gearbox during drive — smooth / slips / jerks / noise:",
        "rt_brakes": "🛑 Brakes under hard stop — straight / pulls left / right:",
        "rt_align": "🎯 Alignment — straight / pulls (which side?):",
        "rt_susp": "🔊 Suspension during drive — quiet / clunk / bounce:",
        "rt_lights": "💡 Warning lights during drive — none / present (which?):",
        "int_dash": "📊 Dashboard lights at startup — none / present (which?):",
        "int_ac": "❄️ AC — blows cold / weak / not working:",
        "int_win": "🪟 Power windows — all work / issues (which?):",
        "int_belts": "🔒 Seat belts — all retract+latch / issues (which seat?):",
        "int_damage": "💥 Interior damage — none / minor / major (describe):",
        "photo_engine": "📸 Photo of engine bay:",
        "photo_under": "📸 Photo of undercarriage:",
        "photo_front": "📸 Front exterior photo:",
        "photo_rear": "📸 Rear exterior photo:",
        "photo_left": "📸 Driver side photo:",
        "photo_right": "📸 Passenger side photo:",
        "photo_interior": "📸 Interior photo (dashboard + seats):",
        "detail": "📝 Describe in more detail:",
        "nego1": "💰 Issue #1 that justifies price reduction:",
        "cost1": "💵 Estimated repair cost for issue #1 (CAD):",
        "nego2": "💰 Issue #2 (or type /skip):",
        "cost2": "💵 Cost for issue #2 (CAD):",
        "nego3": "💰 Issue #3 (or type /skip):",
        "cost3": "💵 Cost for issue #3 (CAD):",
        "nego_args": "🗣 Additional negotiation arguments (or /skip):",
        "overall": "⭐ Overall vehicle condition:",
        "recommend": "👍 Would you recommend buying?",
        "final_comment": "📝 Inspector notes (anything unusual, gut feeling — AI will use this):",
        "pdf_theme": "🎨 Choose PDF theme for the client report:",
        "client_name": "👤 Client name (for report header):",
        "asking_price": "💲 Asking price for the vehicle (CAD):",
        "owners": "👥 Number of previous owners:",
        "service_hist": "📁 Service history — full / partial / none / unknown:",
        "generating": "⏳ Generating report... AI analysis takes ~15 sec.",
        "done": "✅ Report generated and sent to the reports channel!",
        "cancelled": "❌ Inspection cancelled.",
        "skip": "/skip",
    },
    "ru": {
        "welcome": "👋 Добро пожаловать в Argyn Auto Inspection Bot!\n\nЯ проведу тебя по осмотру шаг за шагом.\n\nНапиши /cancel в любой момент чтобы прервать.",
        "vin": "📋 Введи VIN номер:",
        "photo_vin": "📸 Сфотографируй VIN табличку:",
        "ymm": "🚗 Год / Марка / Модель (напр. 2019 BMW 435i):",
        "odo": "🔢 Пробег (км или мили):",
        "photo_odo": "📸 Сфотографируй одометр:",
        "trans": "⚙️ Тип трансмиссии:",
        "keys": "🔑 Количество ключей:",
        "date": "📅 Дата осмотра (напр. 2026-03-07):",
        "location": "📍 Место осмотра (город/адрес):",
        "frame": "🏗 Рама — ровная / следы сварки / деформация:",
        "rust": "🔩 Ржавчина — нет / поверхностная / сквозная (где?):",
        "panel_gaps": "📐 Зазоры — ровные / неровные (какие панели?):",
        "repaint": "🎨 Перекраска — нет / частичная (панели?) / полная:",
        "windshield": "🪟 Лобовое — без повреждений / скол (размер?) / трещина (длина?):",
        "doors": "🚪 Двери — все ок / проблемы (какая дверь, что именно?):",
        "oil": "🛢 Масло — полное+чистое / низкий уровень / тёмное / с примесью:",
        "oil_leak": "💧 Течь масла — нет / капает / сочится (откуда?):",
        "coolant_leak": "🌡 Течь охлаждайки — нет / есть (откуда?):",
        "engine_noise": "🔊 Шум двигателя — тихий / стук / звон / треск (на каких оборотах?):",
        "exhaust": "💨 Дым — нет / белый / синий / чёрный:",
        "cold_start": "❄️ Холодный пуск — плавный / жёсткий / с задержкой / троит:",
        "obd_active": "🔍 Активные коды OBD — нет / есть (перечисли):",
        "obd_pending": "⏳ Отложенные коды — нет / есть (перечисли):",
        "obd_cleared": "🗑 Признаки недавнего сброса кодов — нет / да:",
        "trans_shift": "⚙️ Переключение — плавное / с задержкой / жёсткое / пробуксовка:",
        "trans_leak": "💧 Масло АКПП — чистое+полное / низкий / течь:",
        "brake_front": "🛑 Передние колодки — 1-3мм / 4-6мм / 7мм+:",
        "brake_rear": "🛑 Задние колодки — 1-3мм / 4-6мм / 7мм+:",
        "brake_rotor": "⭕ Диски — гладкие / лёгкие борозды / глубокие / коробление:",
        "brake_vib": "📳 Вибрация при торможении — нет / слабая / сильная:",
        "susp_noise": "🔊 Шум подвески — нет / стук / скрип (где?):",
        "control_arms": "🔧 Рычаги / шаровые — без люфта / небольшой люфт / изношены:",
        "shocks": "🚗 Амортизаторы — работают / мягкие / текут:",
        "steering": "🎯 Руль — чёткий / небольшой люфт / большой люфт:",
        "wheel_bearing": "🔄 Подшипники — тихо / гул (какое колесо?):",
        "tire_front": "🔵 Протектор передних шин (мм, оба колеса):",
        "tire_rear": "🔵 Протектор задних шин (мм, оба колеса):",
        "tire_wear": "📊 Износ — равномерный / внутренний край / внешний край / по центру:",
        "tire_dot": "📅 Год шин (последние 4 цифры DOT кода):",
        "tire_rot": "⚠️ Состояние шин — хорошее / старение / трещины боковины:",
        "tire_match": "✅ Все 4 шины одинаковые — да / нет (что отличается?):",
        "spare": "🔄 Запаска — полноразмерная+накачана / докатка / нет:",
        "batt_volt": "⚡ Напряжение АКБ (двигатель выключен, напр. 12.6В):",
        "batt_age": "📅 Возраст АКБ (лет, или неизвестно):",
        "batt_term": "🔌 Клеммы АКБ — чистые / есть окисление:",
        "rt_engine": "🏎 Двигатель под нагрузкой — плавный / задержка / потеря тяги:",
        "rt_trans": "⚙️ КПП при езде — плавная / пробуксовка / рывки / шум:",
        "rt_brakes": "🛑 Торможение — прямо / тянет влево / тянет вправо:",
        "rt_align": "🎯 Схождение — едет прямо / тянет (в какую сторону?):",
        "rt_susp": "🔊 Подвеска при езде — тихо / стук / пробои:",
        "rt_lights": "💡 Лампы при езде — нет / есть (какие?):",
        "int_dash": "📊 Лампы на панели при запуске — нет / есть (какие?):",
        "int_ac": "❄️ Кондиционер — дует холодно / слабо / не работает:",
        "int_win": "🪟 Стеклоподъёмники — все работают / проблемы (какое?):",
        "int_belts": "🔒 Ремни безопасности — все ок / проблемы (какое место?):",
        "int_damage": "💥 Салон — без повреждений / незначительные / серьёзные (опиши):",
        "photo_engine": "📸 Фото моторного отсека:",
        "photo_under": "📸 Фото днища:",
        "photo_front": "📸 Фото спереди:",
        "photo_rear": "📸 Фото сзади:",
        "photo_left": "📸 Фото со стороны водителя:",
        "photo_right": "📸 Фото со стороны пассажира:",
        "photo_interior": "📸 Фото салона (панель + сиденья):",
        "detail": "📝 Опиши подробнее:",
        "nego1": "💰 Главная проблема №1 для снижения цены\n(конкретно: что, насколько серьёзно — напр. передние диски в разносе, вибрация от 80км/ч):",
        "nego2": "💰 Проблема №2 (или /skip):",
        "nego3": "💰 Проблема №3 (или /skip):",
        "overall": "⭐ Общее состояние автомобиля:",
        "recommend": "👍 Рекомендуешь покупать?",
        "top3": "⚠️ Топ 3 проблемы (каждая с новой строки):",
        "final_comment": "📝 Заметки инспектора (необычное, ощущения — AI использует это):",
        "imm_repair": "🔧 Примерная стоимость немедленного ремонта (CAD):",
        "future_risk": "📅 Примерные расходы в ближайшие 6-12 месяцев (CAD):",
        "pdf_theme": "🎨 Выбери тему PDF для клиента:",
        "client_name": "👤 Имя клиента (для шапки отчёта):",
        "asking_price": "💲 Запрашиваемая цена за машину (CAD):",
        "owners": "👥 Количество предыдущих владельцев:",
        "service_hist": "📁 История обслуживания — полная / частичная / нет / неизвестно:",
        "generating": "⏳ Генерирую отчёт... AI анализ занимает ~15 сек.",
        "done": "✅ Отчёт готов и отправлен в канал отчётов!",
        "cancelled": "❌ Осмотр отменён.",
        "skip": "/skip",
    }
}

def t(ctx, key):
    lang = ctx.user_data.get("lang", "en")
    return T.get(lang, T["en"]).get(key, key)

def kb(*options):
    return ReplyKeyboardMarkup([[o] for o in options], resize_keyboard=True, one_time_keyboard=True)

def kb_row(*options):
    return ReplyKeyboardMarkup([list(options)], resize_keyboard=True, one_time_keyboard=True)

# ─── HANDLERS ─────────────────────────────────────────────

# ─── SECTION BANNERS ──────────────────────────────────────

SECTIONS = {
    "en": {
        2: ("🔍  SECTION 2 of 7: EXTERIOR WALKAROUND",
            "Walk around the vehicle. Take photos from all 4 sides, then check body & tires."),
        3: ("🔧  SECTION 3 of 7: ENGINE BAY",
            "Open the hood. Take an engine photo, then check fluids and engine condition."),
        4: ("🔩  SECTION 4 of 7: UNDERCARRIAGE & BRAKES",
            "Look underneath the vehicle. Check rust, brakes and suspension."),
        5: ("🪑  SECTION 5 of 7: INTERIOR, OBD & BATTERY",
            "Sit inside. Take interior photo, check cabin, plug in OBD scanner, check battery."),
        6: ("🛣️  SECTION 6 of 7: ROAD TEST",
            "Take the car for a drive. Evaluate engine, brakes, handling and suspension."),
        7: ("💰  SECTION 7 of 7: FINDINGS & PRICING",
            "Back at the desk. Enter price reduction issues, costs and final recommendation."),
    },
    "ru": {
        2: ("🔍  РАЗДЕЛ 2 из 7: ЭКСТЕРЬЕР",
            "Обойди машину по кругу. Сфотографируй со всех 4 сторон, затем проверь кузов и шины."),
        3: ("🔧  РАЗДЕЛ 3 из 7: МОТОРНЫЙ ОТСЕК",
            "Открой капот. Сфотографируй мотор, затем проверь жидкости и состояние двигателя."),
        4: ("🔩  РАЗДЕЛ 4 из 7: ДНИЩЕ И ТОРМОЗА",
            "Загляни под машину. Проверь ржавчину, тормоза и подвеску."),
        5: ("🪑  РАЗДЕЛ 5 из 7: САЛОН, OBD И АККУМУЛЯТОР",
            "Садись внутрь. Сфотографируй салон, проверь кабину, подключи OBD сканер, проверь аккумулятор."),
        6: ("🛣️  РАЗДЕЛ 6 из 7: ТЕСТ-ДРАЙВ",
            "Выедь на дорогу. Оцени двигатель, тормоза, управление и подвеску."),
        7: ("💰  РАЗДЕЛ 7 из 7: ПРОБЛЕМЫ И ЦЕНА",
            "Вернись к столу. Введи проблемы для снижения цены, стоимость и итоговую рекомендацию."),
    }
}

async def section_banner(update, ctx, num):
    lang = ctx.user_data.get("lang", "en")
    title, desc = SECTIONS[lang][num]
    text = f"\n{'━'*32}\n{title}\n{'━'*32}\n{desc}"
    await update.message.reply_text(text, reply_markup=ReplyKeyboardRemove())

# ─── HANDLERS ─────────────────────────────────────────────

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ Access denied. Contact admin.")
        return ConversationHandler.END
    ctx.user_data.clear()
    ctx.user_data["data"] = {}
    ctx.user_data["photos"] = {}
    await update.message.reply_text(
        "🌐 Choose language / Выбери язык:",
        reply_markup=kb_row("🇬🇧 English", "🇷🇺 Русский")
    )
    return LANG

# ── SECTION 1: ADMIN ──────────────────────────────────────

async def set_lang(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    lang = "ru" if "ру" in update.message.text.lower() else "en"
    ctx.user_data["lang"] = lang
    ctx.user_data["data"]   = {}
    ctx.user_data["photos"] = {}
    await update.message.reply_text(
        t(ctx, "pdf_theme"),
        reply_markup=kb("☀️ Light / Светлая", "🌙 Dark / Тёмная")
    )
    return PDF_THEME

async def get_pdf_theme(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["pdf_theme"] = "dark" if ("Dark" in update.message.text or "Тём" in update.message.text) else "light"
    lang = ctx.user_data.get("lang", "en")
    title = "📋  РАЗДЕЛ 1 из 7: ДАННЫЕ КЛИЕНТА\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nВведи основную информацию о машине и клиенте." if lang == "ru" else \
            "📋  SECTION 1 of 7: CLIENT & VEHICLE INFO\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nEnter basic information about the vehicle and client."
    await update.message.reply_text(t(ctx, "welcome") + "\n\n" + title, reply_markup=ReplyKeyboardRemove())
    await update.message.reply_text(t(ctx, "client_name"))
    return CLIENT_NAME

async def get_client_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["client_name"] = update.message.text
    await update.message.reply_text(t(ctx, "asking_price"))
    return ASKING_PRICE

async def get_asking_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["asking_price"] = update.message.text
    await update.message.reply_text(t(ctx, "owners"),
        reply_markup=kb("1", "2", "3+"))
    return OWNERS

async def get_owners(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["owners"] = update.message.text
    await update.message.reply_text(t(ctx, "service_hist"),
        reply_markup=kb("✅ Full history / Полная история",
                        "⚠️ Partial / Частичная",
                        "❌ None / Нет"))
    return SERVICE_HIST

async def get_service_hist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["service_hist"] = update.message.text
    await update.message.reply_text(t(ctx, "vin"))
    return VIN

async def get_vin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["vin"] = update.message.text
    await update.message.reply_text(t(ctx, "photo_vin"))
    return PHOTO_VIN

async def get_photo_vin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        ctx.user_data["photos"]["vin"] = update.message.photo[-1].file_id
    await update.message.reply_text(t(ctx, "ymm"))
    return YMM

async def get_ymm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["ymm"] = update.message.text
    await update.message.reply_text(t(ctx, "odo"))
    return ODO

async def get_odo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["odo"] = update.message.text
    await update.message.reply_text(t(ctx, "photo_odo"))
    return PHOTO_ODO

async def get_photo_odo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        ctx.user_data["photos"]["odo"] = update.message.photo[-1].file_id
    await update.message.reply_text(t(ctx, "trans"),
        reply_markup=kb("Automatic / Автомат", "Manual / Механика", "CVT", "DCT"))
    return TRANS

async def get_trans(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["trans"] = update.message.text
    await update.message.reply_text(t(ctx, "keys"),
        reply_markup=kb("1", "2", "3+"))
    return KEYS

async def get_keys(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["keys"] = update.message.text
    await update.message.reply_text(t(ctx, "date"))
    return DATE

async def get_date(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["date"] = update.message.text
    await update.message.reply_text(t(ctx, "location"))
    return LOCATION

async def get_location(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["location"] = update.message.text
    await section_banner(update, ctx, 2)
    await update.message.reply_text(t(ctx, "photo_front"))
    return PHOTO_FRONT

# ─── UNIVERSAL DETAIL SYSTEM ──────────────────────────────
# Fields that need follow-up when ⚠️ or ❌ is selected
# Format: field_key -> (EN question, RU question)
DETAIL_QUESTIONS = {
    "oil_leak":      ("Where is the leak from? (e.g. valve cover, oil pan, rear main seal)",
                      "Откуда течёт? (напр. клапанная крышка, поддон, задний сальник)"),
    "coolant_leak":  ("Where is the leak from? (e.g. radiator, hose, water pump)",
                      "Откуда течёт? (напр. радиатор, шланг, водяной насос)"),
    "engine_noise":  ("Describe the noise: type, when it occurs (e.g. knock on startup, tick at idle)",
                      "Опиши шум: тип, когда возникает (напр. стук при запуске, тик на холостых)"),
    "exhaust":       ("What colour is the smoke and when does it appear?",
                      "Какой цвет дыма и когда появляется?"),
    "obd_active":    ("List the fault codes (e.g. P0300, P0420):",
                      "Перечисли коды неисправностей (напр. P0300, P0420):"),
    "rust":          ("Where is the rust located? How severe? (e.g. rear subframe, floor panels)",
                      "Где находится ржавчина? Насколько серьёзная? (напр. подрамник, полы)"),
    "frame":         ("Where is the damage? Describe (e.g. bent rail front left, weld marks)",
                      "Где повреждение? Опиши (напр. погнута лонжерона спереди слева, следы сварки)"),
    "repaint":       ("Which panels/elements are repainted? (e.g. driver door, front bumper)",
                      "Какие панели/элементы перекрашены? (напр. дверь водителя, передний бампер)"),
    "susp_noise":    ("Where does the noise come from and what type? (e.g. front left clunk over bumps)",
                      "Откуда шум и какой тип? (напр. стук спереди слева на кочках)"),
    "control_arms":  ("Which side? What is the condition? (e.g. both front, loose bushings)",
                      "Какая сторона? Состояние? (напр. обе передние, разбитые втулки)"),
    "shocks":        ("Which shocks are leaking? (e.g. front left, rear both)",
                      "Какие амортизаторы текут? (напр. передний левый, задние оба)"),
    "steering":      ("Describe the play: amount, any noises? (e.g. 3cm of play, clunk turning left)",
                      "Опиши люфт: величина, есть ли звуки? (напр. 3см люфт, стук при повороте влево)"),
    "wheel_bearing": ("Which wheel? What sound? (e.g. front right hum at speed)",
                      "Какое колесо? Какой звук? (напр. правое переднее гудит на скорости)"),
    "brake_front":   ("Approximate thickness in mm? Any grooves on rotors?",
                      "Примерная толщина в мм? Есть ли борозды на дисках?"),
    "brake_rear":    ("Approximate thickness in mm? Any grooves on rotors?",
                      "Примерная толщина в мм? Есть ли борозды на дисках?"),
    "brake_rotor":   ("Describe: which rotors, how deep are the grooves?",
                      "Опиши: какие диски, насколько глубокие борозды?"),
    "brake_vib":     ("When does vibration occur? Front or rear? (e.g. heavy braking from highway speed)",
                      "Когда возникает вибрация? Спереди или сзади? (напр. при сильном торможении)"),
    "rt_lights":     ("Which warning lights? (e.g. ABS, check engine, traction control)",
                      "Какие предупредительные лампы? (напр. ABS, check engine, антипробукс)"),
    "rt_susp":       ("Where does the noise come from during drive? (e.g. front left over bumps)",
                      "Откуда шум во время езды? (напр. спереди слева на кочках)"),
    "rt_brakes":     ("Describe: soft pedal, pull to one side, noise?",
                      "Опиши: мягкая педаль, уводит в сторону, шум?"),
    "int_damage":    ("Where and what type of damage? (e.g. torn rear seat, cracked dash)",
                      "Где и какой тип повреждения? (напр. порван задний диван, трещина на панели)"),
    "int_dash":      ("Which warning lights on dashboard?",
                      "Какие предупредительные лампы на панели?"),
    "trans_shift":   ("Describe the issue: delay, jerk, which gear? (e.g. hard shift 1-2, delay in reverse)",
                      "Опиши проблему: задержка, толчок, какая передача? (напр. толчок 1-2, задержка задней)"),
    "trans_leak":    ("Where is the leak from? (e.g. pan gasket, output shaft seal)",
                      "Откуда течёт? (напр. прокладка поддона, сальник вала)"),
    "batt_term":     ("Describe corrosion level and which terminal (e.g. heavy blue corrosion on positive)",
                      "Опиши уровень коррозии и какая клемма (напр. сильная коррозия на плюсе)"),
}

def needs_detail(field, value):
    """Returns True if this field+value needs a follow-up detail question"""
    if field not in DETAIL_QUESTIONS:
        return False
    return "⚠️" in value or "❌" in value

async def _save_and_maybe_detail(update, ctx, field, next_state, next_fn):
    """Save field value, ask for detail if needed, otherwise proceed"""
    val = update.message.text
    ctx.user_data["data"][field] = val
    if needs_detail(field, val):
        lang = ctx.user_data.get("lang", "en")
        en_q, ru_q = DETAIL_QUESTIONS[field]
        question = ru_q if lang == "ru" else en_q
        ctx.user_data["_detail_field"] = field
        ctx.user_data["_detail_next_state"] = next_state
        ctx.user_data["_detail_next_fn"] = next_fn
        await update.message.reply_text(f"📝 {question}", reply_markup=ReplyKeyboardRemove())
        return DETAIL
    await next_fn()
    return next_state

async def get_detail(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle follow-up detail answer"""
    field = ctx.user_data.get("_detail_field", "")
    if field:
        base = ctx.user_data["data"].get(field, "")
        ctx.user_data["data"][field] = base + "\n→ " + update.message.text
    next_state = ctx.user_data.get("_detail_next_state", ConversationHandler.END)
    next_fn = ctx.user_data.get("_detail_next_fn")
    if next_fn:
        await next_fn()
    return next_state


# ── SECTION 2: EXTERIOR ───────────────────────────────────

async def get_photo_front(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        ctx.user_data["photos"]["front"] = update.message.photo[-1].file_id
    await update.message.reply_text(t(ctx, "photo_rear"))
    return PHOTO_REAR

async def get_photo_rear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        ctx.user_data["photos"]["rear"] = update.message.photo[-1].file_id
    await update.message.reply_text(t(ctx, "photo_left"))
    return PHOTO_LEFT

async def get_photo_left(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        ctx.user_data["photos"]["left"] = update.message.photo[-1].file_id
    await update.message.reply_text(t(ctx, "photo_right"))
    return PHOTO_RIGHT

async def get_photo_right(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        ctx.user_data["photos"]["right"] = update.message.photo[-1].file_id
    await update.message.reply_text(t(ctx, "frame"),
        reply_markup=kb("✅ Good / Хорошее", "⚠️ Minor damage / Мелкие повреждения", "❌ Structural damage / Структурные повреждения"))
    return FRAME

async def get_panel_gaps(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["panel_gaps"] = update.message.text
    await update.message.reply_text(t(ctx, "repaint"),
        reply_markup=kb("✅ No / Нет", "⚠️ Minor chips / Мелкие сколы", "❌ Repainted / Перекрашено"))
    return REPAINT

async def get_repaint(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await _save_and_maybe_detail(update, ctx, "repaint", WINDSHIELD,
        lambda: update.message.reply_text(t(ctx, "windshield"),
            reply_markup=kb("✅ Good / Хорошее", "⚠️ Minor chips / Мелкие сколы", "❌ Crack / Трещина")))

async def get_windshield(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["windshield"] = update.message.text
    await update.message.reply_text(t(ctx, "doors"),
        reply_markup=kb("✅ Normal / Норма", "⚠️ Minor issues / Мелкие проблемы", "❌ Damaged / Повреждены"))
    return DOORS

async def get_doors(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["doors"] = update.message.text
    await update.message.reply_text(t(ctx, "tire_front"), reply_markup=ReplyKeyboardRemove())
    return TIRE_FRONT

# ── TIRES ─────────────────────────────────────────────────

async def get_tire_front(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["tire_front"] = update.message.text
    await update.message.reply_text(t(ctx, "tire_rear"), reply_markup=ReplyKeyboardRemove())
    return TIRE_REAR

async def get_tire_rear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["tire_rear"] = update.message.text
    await update.message.reply_text(t(ctx, "tire_wear"),
        reply_markup=kb("✅ Even / Равномерный", "⚠️ Uneven / Неравномерный", "❌ Severe / Сильный"))
    return TIRE_WEAR

async def get_tire_wear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["tire_wear"] = update.message.text
    await update.message.reply_text(t(ctx, "tire_dot"), reply_markup=ReplyKeyboardRemove())
    return TIRE_DOT

async def get_tire_dot(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["tire_dot"] = update.message.text
    await update.message.reply_text(t(ctx, "tire_rot"),
        reply_markup=kb("✅ No / Нет", "⚠️ Minor / Незначительные", "❌ Yes / Да"))
    return TIRE_ROT

async def get_tire_rot(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["tire_rot"] = update.message.text
    await update.message.reply_text(t(ctx, "tire_match"),
        reply_markup=kb("✅ Yes / Да", "❌ No / Нет"))
    return TIRE_MATCH

async def get_tire_match(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["tire_match"] = update.message.text
    await update.message.reply_text(t(ctx, "spare"),
        reply_markup=kb("✅ Yes / Да", "⚠️ Compact / Докатка", "❌ No / Нет"))
    return SPARE

async def get_spare(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["spare"] = update.message.text
    await section_banner(update, ctx, 3)
    await update.message.reply_text(t(ctx, "photo_engine"))
    return PHOTO_ENGINE

# ── SECTION 3: ENGINE BAY ─────────────────────────────────

async def get_photo_engine(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        ctx.user_data["photos"]["engine"] = update.message.photo[-1].file_id
    await update.message.reply_text(t(ctx, "oil"),
        reply_markup=kb("✅ Full / Полный", "⚠️ Low / Низкий", "❌ Very low / Очень низкий"))
    return OIL

async def get_oil(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["oil"] = update.message.text
    await update.message.reply_text(t(ctx, "oil_leak"),
        reply_markup=kb("✅ None / Нет", "⚠️ Minor / Незначительная", "❌ Active leak / Активная"))
    return OIL_LEAK

async def get_oil_leak(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await _save_and_maybe_detail(update, ctx, "oil_leak", COOLANT_LEAK,
        lambda: update.message.reply_text(t(ctx, "coolant_leak"),
            reply_markup=kb("✅ None / Нет", "⚠️ Minor / Незначительная", "❌ Active leak / Активная")))

async def get_coolant_leak(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await _save_and_maybe_detail(update, ctx, "coolant_leak", ENGINE_NOISE,
        lambda: update.message.reply_text(t(ctx, "engine_noise"),
            reply_markup=kb("✅ Normal / Нормальный", "⚠️ Minor noise / Незначительный", "❌ Loud / Громкий")))

async def get_engine_noise(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await _save_and_maybe_detail(update, ctx, "engine_noise", EXHAUST,
        lambda: update.message.reply_text(t(ctx, "exhaust"),
            reply_markup=kb("✅ Clean / Чистый", "⚠️ Light smoke / Лёгкий дым", "❌ Heavy smoke / Сильный дым")))

async def get_exhaust(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await _save_and_maybe_detail(update, ctx, "exhaust", COLD_START,
        lambda: update.message.reply_text(t(ctx, "cold_start"),
            reply_markup=kb("✅ Smooth / Плавный", "⚠️ Rough / Неровный", "❌ Failed / Не завёлся")))

async def get_cold_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["cold_start"] = update.message.text
    await section_banner(update, ctx, 4)
    await update.message.reply_text(t(ctx, "photo_under"))
    return PHOTO_UNDER

# ── SECTION 4: UNDERCARRIAGE & BRAKES ─────────────────────

async def get_photo_under(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        ctx.user_data["photos"]["under"] = update.message.photo[-1].file_id
    await update.message.reply_text(t(ctx, "rust"),
        reply_markup=kb("✅ No rust / Нет ржавчины", "⚠️ Surface rust / Поверхностная", "❌ Structural rust / Структурная"))
    return RUST

async def get_frame(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await _save_and_maybe_detail(update, ctx, "frame", PANEL_GAPS,
        lambda: update.message.reply_text(t(ctx, "panel_gaps"),
            reply_markup=kb("✅ Even / Ровные", "⚠️ Minor gaps / Мелкие зазоры", "❌ Major misalignment / Большое смещение")))

async def get_rust(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await _save_and_maybe_detail(update, ctx, "rust", BRAKE_FRONT,
        lambda: update.message.reply_text(t(ctx, "brake_front"), reply_markup=kb("✅ Good / Хорошие (>6mm)", "⚠️ Worn / Изношены (3-6mm)", "❌ Critical / Критично (<3mm)")))

async def get_brake_front(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await _save_and_maybe_detail(update, ctx, "brake_front", BRAKE_REAR,
        lambda: update.message.reply_text(t(ctx, "brake_rear"), reply_markup=kb("✅ Good / Хорошие (>6mm)", "⚠️ Worn / Изношены (3-6mm)", "❌ Critical / Критично (<3mm)")))

async def get_brake_rear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await _save_and_maybe_detail(update, ctx, "brake_rear", BRAKE_ROTOR,
        lambda: update.message.reply_text(t(ctx, "brake_rotor"), reply_markup=kb("✅ Good / Хорошие", "⚠️ Grooved / Нарезаны", "❌ Damaged / Повреждены")))

async def get_brake_rotor(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await _save_and_maybe_detail(update, ctx, "brake_rotor", SUSP_NOISE,
        lambda: update.message.reply_text(t(ctx, "susp_noise"), reply_markup=kb("✅ None / Нет", "⚠️ Minor / Незначительный", "❌ Loud clunk / Громкий стук")))

async def get_susp_noise(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await _save_and_maybe_detail(update, ctx, "susp_noise", CONTROL_ARMS,
        lambda: update.message.reply_text(t(ctx, "control_arms"), reply_markup=kb("✅ Good / Хорошие", "⚠️ Worn / Изношены", "❌ Damaged / Повреждены")))

async def get_control_arms(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await _save_and_maybe_detail(update, ctx, "control_arms", SHOCKS,
        lambda: update.message.reply_text(t(ctx, "shocks"), reply_markup=kb("✅ No leaks / Нет течи", "⚠️ Weeping / Незначительная", "❌ Leaking / Текут")))

async def get_shocks(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await _save_and_maybe_detail(update, ctx, "shocks", STEERING,
        lambda: update.message.reply_text(t(ctx, "steering"), reply_markup=kb("✅ None / Нет", "⚠️ Minor play / Незначительный", "❌ Excessive play / Большой люфт")))

async def get_steering(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await _save_and_maybe_detail(update, ctx, "steering", WHEEL_BEARING,
        lambda: update.message.reply_text(t(ctx, "wheel_bearing"), reply_markup=kb("✅ None / Нет", "⚠️ Minor / Незначительный", "❌ Loud / Громкий")))

async def get_wheel_bearing(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["wheel_bearing"] = update.message.text
    await section_banner(update, ctx, 5)
    await update.message.reply_text(t(ctx, "photo_interior"))
    return PHOTO_INTERIOR

# ── SECTION 5: INTERIOR, OBD & BATTERY ───────────────────

async def get_photo_interior(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        ctx.user_data["photos"]["interior"] = update.message.photo[-1].file_id
    await update.message.reply_text(t(ctx, "int_dash"),
        reply_markup=kb("✅ None / Нет", "⚠️ Minor / Незначительные", "❌ Multiple / Несколько"))
    return INT_DASH

async def get_int_dash(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await _save_and_maybe_detail(update, ctx, "int_dash", INT_AC,
        lambda: update.message.reply_text(t(ctx, "int_ac"), reply_markup=kb("✅ Working / Работает", "⚠️ Weak / Слабый", "❌ Not working / Не работает")))

async def get_int_ac(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["int_ac"] = update.message.text
    await update.message.reply_text(t(ctx, "int_win"),
        reply_markup=kb("✅ All working / Все работают", "⚠️ One issue / Одна проблема", "❌ Multiple issues / Несколько"))
    return INT_WIN

async def get_int_win(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["int_win"] = update.message.text
    await update.message.reply_text(t(ctx, "int_belts"),
        reply_markup=kb("✅ Good / Хорошие", "⚠️ Worn / Изношены", "❌ Damaged / Повреждены"))
    return INT_BELTS

async def get_int_belts(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["int_belts"] = update.message.text
    await update.message.reply_text(t(ctx, "int_damage"),
        reply_markup=kb("✅ None / Нет", "⚠️ Minor / Мелкие", "❌ Major damage / Серьёзные"))
    return INT_DAMAGE

async def get_int_damage(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await _save_and_maybe_detail(update, ctx, "int_damage", BATT_VOLT,
        lambda: update.message.reply_text(t(ctx, "batt_volt"), reply_markup=ReplyKeyboardRemove()))

async def get_batt_volt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["batt_volt"] = update.message.text
    await update.message.reply_text(t(ctx, "batt_age"),
        reply_markup=kb("✅ Under 3 years / До 3 лет", "⚠️ 3-5 years / 3-5 лет", "❌ Over 5 years / Более 5 лет"))
    return BATT_AGE

async def get_batt_age(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["batt_age"] = update.message.text
    await update.message.reply_text(t(ctx, "batt_term"),
        reply_markup=kb("✅ Clean / Чистые", "⚠️ Minor corrosion / Незначительная коррозия", "❌ Heavy corrosion / Сильная коррозия"))
    return BATT_TERM

async def get_batt_term(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await _save_and_maybe_detail(update, ctx, "batt_term", OBD_ACTIVE,
        lambda: update.message.reply_text(t(ctx, "obd_active"), reply_markup=kb("✅ None / Нет", "⚠️ 1-2 codes / 1-2 кода", "❌ Multiple / Несколько")))

async def get_obd_active(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await _save_and_maybe_detail(update, ctx, "obd_active", OBD_PENDING,
        lambda: update.message.reply_text(t(ctx, "obd_pending"), reply_markup=kb("✅ None / Нет", "⚠️ Present / Есть")))

async def get_obd_pending(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["obd_pending"] = update.message.text
    await update.message.reply_text(t(ctx, "obd_cleared"),
        reply_markup=kb("✅ No / Нет", "⚠️ Possibly / Возможно", "❌ Yes / Да"))
    return OBD_CLEARED

async def get_obd_cleared(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["obd_cleared"] = update.message.text
    await update.message.reply_text(t(ctx, "trans_shift"),
        reply_markup=kb("✅ Smooth / Плавное", "⚠️ Slight delay / Небольшая задержка", "❌ Rough / Жёсткое"))
    return TRANS_SHIFT

async def get_trans_shift(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await _save_and_maybe_detail(update, ctx, "trans_shift", TRANS_LEAK,
        lambda: update.message.reply_text(t(ctx, "trans_leak"), reply_markup=kb("✅ None / Нет", "⚠️ Minor / Незначительная", "❌ Active leak / Активная")))

async def get_trans_leak(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["trans_leak"] = update.message.text
    await section_banner(update, ctx, 6)
    await update.message.reply_text(t(ctx, "rt_engine"),
        reply_markup=kb("✅ Smooth / Плавная", "⚠️ Minor issues / Мелкие", "❌ Rough / Нестабильная"))
    return RT_ENGINE

# ── SECTION 6: ROAD TEST ──────────────────────────────────

async def get_rt_engine(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["rt_engine"] = update.message.text
    await update.message.reply_text(t(ctx, "rt_trans"),
        reply_markup=kb("✅ Smooth / Плавная", "⚠️ Slight delay / Задержка", "❌ Rough / Жёсткая"))
    return RT_TRANS

async def get_rt_trans(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["rt_trans"] = update.message.text
    await update.message.reply_text(t(ctx, "rt_brakes"),
        reply_markup=kb("✅ Normal / Норма", "⚠️ Soft / Мягкие", "❌ Pull / Уводит"))
    return RT_BRAKES

async def get_rt_brakes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await _save_and_maybe_detail(update, ctx, "rt_brakes", BRAKE_VIB,
        lambda: update.message.reply_text(t(ctx, "brake_vib"), reply_markup=kb("✅ None / Нет", "⚠️ Minor / Незначительная", "❌ Strong / Сильная")))

async def get_brake_vib(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await _save_and_maybe_detail(update, ctx, "brake_vib", RT_ALIGN,
        lambda: update.message.reply_text(t(ctx, "rt_align"), reply_markup=kb("✅ Straight / Прямо", "⚠️ Minor pull / Незначительно уводит", "❌ Strong pull / Сильно уводит")))

async def get_rt_align(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["rt_align"] = update.message.text
    await update.message.reply_text(t(ctx, "rt_susp"),
        reply_markup=kb("✅ None / Нет", "⚠️ Minor / Незначительный", "❌ Loud / Громкий"))
    return RT_SUSP

async def get_rt_susp(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await _save_and_maybe_detail(update, ctx, "rt_susp", RT_LIGHTS,
        lambda: update.message.reply_text(t(ctx, "rt_lights"), reply_markup=kb("✅ None / Нет", "⚠️ 1 light / 1 лампа", "❌ Multiple / Несколько")))

async def get_rt_lights(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["rt_lights"] = update.message.text
    await section_banner(update, ctx, 7)
    await update.message.reply_text(t(ctx, "nego1"), reply_markup=ReplyKeyboardRemove())
    return NEGO1

# ── SECTION 7: FINDINGS ──────────────────────────────────

async def get_nego1(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["nego1"] = update.message.text
    lang = ctx.user_data.get("lang", "en")
    hint = " (или /skip)" if lang == "ru" else " (or /skip)"
    await update.message.reply_text(t(ctx, "nego2") + hint)
    return NEGO2

async def get_nego2(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text.strip() == "/skip":
        ctx.user_data["data"]["nego2"] = ""
        ctx.user_data["data"]["nego3"] = ""
        await update.message.reply_text(t(ctx, "overall"),
            reply_markup=kb("✅ Good condition / Хорошее", "⚠️ Acceptable / Приемлемое", "❌ High risk / Высокий риск"))
        return OVERALL
    ctx.user_data["data"]["nego2"] = update.message.text
    lang = ctx.user_data.get("lang", "en")
    hint = " (или /skip)" if lang == "ru" else " (or /skip)"
    await update.message.reply_text(t(ctx, "nego3") + hint)
    return NEGO3

async def get_nego3(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text.strip() == "/skip":
        ctx.user_data["data"]["nego3"] = ""
    else:
        ctx.user_data["data"]["nego3"] = update.message.text
    await update.message.reply_text(t(ctx, "overall"),
        reply_markup=kb("✅ Good condition / Хорошее", "⚠️ Acceptable / Приемлемое", "❌ High risk / Высокий риск"))
    return OVERALL

async def get_overall(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["overall"] = update.message.text
    await update.message.reply_text(t(ctx, "recommend"),
        reply_markup=kb("✅ Yes / Да", "⚠️ Yes, but negotiate / Да, но торгуйтесь", "❌ No / Нет"))
    return RECOMMEND

async def get_recommend(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["recommend"] = update.message.text
    await update.message.reply_text(t(ctx, "final_comment"), reply_markup=ReplyKeyboardRemove())
    return FINAL_COMMENT

async def get_final_comment(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["data"]["final_comment"] = update.message.text
    await update.message.reply_text(t(ctx, "generating"), reply_markup=ReplyKeyboardRemove())
    try:
        await _generate_and_send(update, ctx)
    except Exception as e:
        await update.message.reply_text(f"❌ Error generating PDF: {str(e)[:300]}")
        import traceback
        traceback.print_exc()
    return ConversationHandler.END

async def _save_to_supabase(report_id: str, d: dict, photo_b64: dict,
                            grade: dict, ai_text: str) -> bool:
    """Save inspection report to Supabase. Returns True on success."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False
    import json
    # Store photo keys only (not base64 data - too large)
    photo_keys = {k: True for k, v in photo_b64.items() if v}
    payload = {
        "id":              report_id,
        "vin":             d.get("vin", ""),
        "ymm":             d.get("ymm", ""),
        "client_name":     d.get("client_name", ""),
        "location":        d.get("location", ""),
        "inspection_date": d.get("date", ""),
        "grade":           grade["letter"],
        "ai_text":         ai_text or "",
        "data":            d,
        "photos":          photo_b64,  # full base64 for web report
    }
    # Try without photos first if payload is too large
    try:
        import httpx
        payload_str = json.dumps(payload)
        # If over 500KB, strip photos
        if len(payload_str) > 500_000:
            payload["photos"] = photo_keys
            payload_str = json.dumps(payload)

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{SUPABASE_URL}/rest/v1/reports",
                headers={
                    "apikey":        SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type":  "application/json",
                    "Prefer":        "return=minimal",
                },
                content=payload_str
            )
            if resp.status_code in (200, 201):
                return True
            err_msg = f"Supabase save error: {resp.status_code} {resp.text[:200]}"
            print(err_msg)
            return False
    except Exception as e:
        print(f"Supabase save error: {e}")
        return False


# ─── PDF GENERATION ───────────────────────────────────────

async def _generate_and_send(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    d = ctx.user_data["data"]
    photos = ctx.user_data["photos"]
    bot = ctx.bot

    # Download photos and convert to base64
    import base64
    photo_b64 = {}
    for key, file_id in photos.items():
        try:
            f = await bot.get_file(file_id)
            bio = BytesIO()
            await f.download_to_memory(bio)
            bio.seek(0)
            photo_b64[key] = "data:image/jpeg;base64," + base64.b64encode(bio.read()).decode()
        except Exception:
            photo_b64[key] = ""

    # Grade
    overall = d.get("overall", "").lower()
    if "good" in overall or "хорошее" in overall:
        grade = {"letter": "A", "label": "Good Condition", "color": "#22C55E"}
    elif "high risk" in overall or "высокий" in overall:
        grade = {"letter": "C", "label": "High Risk -- Avoid", "color": "#EF4444"}
    else:
        grade = {"letter": "B", "label": "Acceptable -- Negotiate", "color": "#F97316"}

    now = datetime.now()
    vin = d.get("vin", "NOVIN")
    report_id = f"AA-{now.strftime('%Y%m%d')}-{vin[-4:]}"

    # Get AI analysis
    ai_text = await _get_ai_analysis(d)

    # Generate PDF using reportlab
    theme = ctx.user_data.get("pdf_theme", "light")
    pdf_bytes = _build_pdf_reportlab(d, photo_b64, grade, report_id, now, ai_text=ai_text, theme=theme)
    pdf_bio = BytesIO(pdf_bytes)
    pdf_bio.name = f"ARGYN_AUTO_{vin}_{now.strftime('%Y%m%d')}.pdf"
    pdf_bio.seek(0)

    # Save to Supabase and generate report link
    saved = await _save_to_supabase(report_id, d, photo_b64, grade, ai_text)
    report_url = f"{SITE_URL}/report/{report_id}" if saved else None

    # Send to report channel
    caption = (
        f"📋 *New Inspection Report*\n"
        f"🚗 {d.get('ymm','--')}\n"
        f"🔑 VIN: `{vin}`\n"
        f"📍 {d.get('location','--')}\n"
        f"👤 Client: {d.get('client_name','--')}\n"
        f"⭐ Grade: *{grade['letter']}* -- {grade['label']}\n"
    )
    if report_url:
        caption += f"🌐 [View Report]({report_url})"

    await bot.send_document(
        chat_id=REPORT_CHAT,
        document=pdf_bio,
        caption=caption,
        parse_mode="Markdown",
        filename=pdf_bio.name
    )

    # Send report link to inspector
    done_msg = t(ctx, "done")
    if report_url:
        done_msg += f"\n\n🌐 Report link (send to client):\n{report_url}"
    await update.message.reply_text(done_msg)






async def _get_ai_analysis(d: dict) -> str:
    """Call Claude API to get full AI market + repair analysis"""
    import httpx, os
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return ""

    # --- Pull all inspection data ---
    ymm           = d.get("ymm", "Unknown vehicle")
    odo           = d.get("odo", "unknown")
    location      = d.get("location", "Canada")
    vin           = d.get("vin", "")
    asking        = d.get("asking_price", "")
    owners        = d.get("owners", "")
    service_hist  = d.get("service_hist", "")
    trans_type    = d.get("trans", "")
    # Exterior
    frame         = d.get("frame", "")
    panel_gaps    = d.get("panel_gaps", "")
    repaint       = d.get("repaint", "")
    windshield    = d.get("windshield", "")
    doors         = d.get("doors", "")
    # Tires
    tire_front    = d.get("tire_front", "")
    tire_rear     = d.get("tire_rear", "")
    tire_wear     = d.get("tire_wear", "")
    tire_dot      = d.get("tire_dot", "")
    tire_rot      = d.get("tire_rot", "")
    spare         = d.get("spare", "")
    # Engine
    oil           = d.get("oil", "")
    oil_leak      = d.get("oil_leak", "")
    coolant_leak  = d.get("coolant_leak", "")
    engine_noise  = d.get("engine_noise", "")
    exhaust       = d.get("exhaust", "")
    cold_start    = d.get("cold_start", "")
    # Undercarriage
    rust          = d.get("rust", "")
    brake_front   = d.get("brake_front", "")
    brake_rear    = d.get("brake_rear", "")
    brake_rotor   = d.get("brake_rotor", "")
    brake_vib     = d.get("brake_vib", "")
    susp_noise    = d.get("susp_noise", "")
    control_arms  = d.get("control_arms", "")
    shocks        = d.get("shocks", "")
    steering      = d.get("steering", "")
    wheel_bearing = d.get("wheel_bearing", "")
    # Interior / OBD / Battery
    int_dash      = d.get("int_dash", "")
    int_ac        = d.get("int_ac", "")
    batt_volt     = d.get("batt_volt", "")
    batt_age      = d.get("batt_age", "")
    obd_active    = d.get("obd_active", "")
    obd_pending   = d.get("obd_pending", "")
    obd_cleared   = d.get("obd_cleared", "")
    trans_shift   = d.get("trans_shift", "")
    trans_leak    = d.get("trans_leak", "")
    # Road test
    rt_engine     = d.get("rt_engine", "")
    rt_trans      = d.get("rt_trans", "")
    rt_brakes     = d.get("rt_brakes", "")
    rt_align      = d.get("rt_align", "")
    rt_susp       = d.get("rt_susp", "")
    # Findings
    nego1         = d.get("nego1", "")
    cost1         = d.get("cost1", "")
    nego2         = d.get("nego2", "")
    cost2         = d.get("cost2", "")
    nego3         = d.get("nego3", "")
    cost3         = d.get("cost3", "")
    overall       = d.get("overall", "")
    imm_repair    = d.get("imm_repair", "")
    future_risk   = d.get("future_risk", "")

    # Build issues list with costs
    issues_lines = []
    for item, cost in [(nego1, cost1), (nego2, cost2), (nego3, cost3)]:
        if item:
            issues_lines.append(f"  - {item}" + (f" (~${cost} CAD)" if cost else ""))
    issues_str = "\n".join(issues_lines) or "  None reported"

    prompt = f"""You are a senior Canadian automotive analyst with deep knowledge of used car prices and repair costs in Canada.

=== VEHICLE ===
{ymm} | VIN: {vin}
Odometer: {odo} | Transmission: {trans_type}
Asking price: ${asking} CAD | Owners: {owners} | Service history: {service_hist}
Location: {location}

=== EXTERIOR ===
Frame: {frame} | Panel gaps: {panel_gaps} | Repaint: {repaint}
Windshield: {windshield} | Doors: {doors}

=== TIRES ===
Front: {tire_front} | Rear: {tire_rear} | Wear pattern: {tire_wear}
DOT year: {tire_dot} | Dry rot: {tire_rot} | Spare: {spare}

=== ENGINE BAY ===
Oil: {oil} | Oil leaks: {oil_leak} | Coolant leaks: {coolant_leak}
Engine noise: {engine_noise} | Exhaust smoke: {exhaust} | Cold start: {cold_start}

=== UNDERCARRIAGE & BRAKES ===
Rust: {rust}
Front brakes: {brake_front} | Rear brakes: {brake_rear}
Rotors: {brake_rotor} | Brake vibration: {brake_vib}
Suspension noise: {susp_noise} | Control arms: {control_arms}
Shocks: {shocks} | Steering: {steering} | Wheel bearings: {wheel_bearing}

=== INTERIOR / OBD / BATTERY ===
Dashboard: {int_dash} | A/C: {int_ac}
Battery: {batt_volt} / {batt_age}
OBD active codes: {obd_active} | Pending: {obd_pending} | Recently cleared: {obd_cleared}
Transmission shifts: {trans_shift} | Trans leak: {trans_leak}

=== ROAD TEST ===
Engine: {rt_engine} | Transmission: {rt_trans} | Brakes: {rt_brakes}
Alignment: {rt_align} | Suspension: {rt_susp}

=== ISSUES FOUND ===
{issues_str}
Immediate repairs needed: {imm_repair}
Next 6-12 months: {future_risk}
Overall condition: {overall}

=== YOUR TASK ===
Provide analysis with EXACTLY these 5 headers. No text before first header.

MARKET VALUE: Current fair market value range in CAD for this exact vehicle and condition. Reference current Canadian used car market.

DEPRECIATION: Expected value loss over next 1-2 years. Give specific dollar amount and percentage based on make/model/mileage trends.

REPAIR COST ESTIMATE: Itemized repair costs in CAD using Canadian labour rates ($120-160/hr) and OEM/aftermarket parts. List each issue with realistic price range. Total immediate cost and total 6-12 month cost.

RISK ASSESSMENT: Key financial and mechanical risks based on ALL findings above. Flag any combinations that suggest hidden damage (e.g. cleared codes + repaint + multiple owners). Max 3 sentences.

FINAL VERDICT: One sentence -- recommended offer price in CAD and action (buy at $X, negotiate to $X, or walk away). Base the offer price on: asking price minus repair costs minus a reasonable market discount.

Rules: CAD prices only. Be specific with real market numbers. Do not include negotiation tactics. Max 3 sentences per section. Use regular hyphens (-) not em-dashes."""

    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-sonnet-4-5-20251022",
                        "max_tokens": 900,
                        "messages": [{"role": "user", "content": prompt}]
                    }
                )
                data = resp.json()
                if "content" in data:
                    return data["content"][0]["text"]
                print(f"AI API error (attempt {attempt+1}): {data}")
        except Exception as e:
            print(f"AI API exception (attempt {attempt+1}): {e}")
    return ""


def _img_from_b64(b64_str, width_mm, height_mm):
    """Convert base64 image to ReportLab Image"""
    import base64
    from reportlab.platypus import Image as RLImage
    from reportlab.lib.units import mm
    if not b64_str:
        return None
    try:
        data = base64.b64decode(b64_str.split(",")[1])
        return RLImage(BytesIO(data), width=width_mm*mm, height=height_mm*mm)
    except Exception:
        return None


ARGYN_LOGO_B64 = "iVBORw0KGgoAAAANSUhEUgAAASwAAACgCAYAAAC2eFFiAADulUlEQVR4nKz9V7Akx5EuDH4emVm6jj6ntZZoAa01CC0JECAICgzV3OGdueI3W7Pfdm3t392HfVtbYWtr947iDDkUAEmAECQkobXWaDTQjW607tNHq5KZGb4PITIyq84BbW0Thj5VlZkhPDzcP/fw8KDC0EZ4EAAIxAATAADMDAAgMKB/k2AwAA+eekY9CCKCJPWdiAD9rrmIKHkeujhmCBAkO7/r59zLtENwxy0QERiAJICEepc4eSf7rBBCt4OBLnWl+k0E1n1KtVs/Y9pK6uHUu2DPPm371NEBAjMBcMoignTKdttEpMeIBJjjjuYTeZnnqaMcyQwI9XuWRu6zzASCek5Kqe+LLKlS77hlGh4wtDNjY9ol02TQf5Zuk/4BDIKQuhwBQPNu6nlWfMssAVOb6D7eaVoQAAGibrzIirnAYHjovEhPHkq+Oz11x5hIQELRGfoVgiq+K4/p+ZWlxWLP2nEQak4TqzoECcWrzEmfSdFelca2/cwSTGznGBFAEABTiveYGKx52JTpwYPQ35l13zuGspM/VdOkva/KE/YzEcEnyWCSAISamDI9+KoLRhiw6pYASKo3WBNTPc56AieTzGVC9UgyoJLVCCXtZs3ouoMMJRAzvTW3Yk0oQQSWbNvrXmbCMADJ0oyQFaouMVLCCordjHCFGTiH2KwnpW2zVNyn5jbbAe0miE1HyCGAFfipZ9jWmUxMpNoOKGWSIhCp3wSRmWeqji7CvON3TgtqOMycFobORGd2FAGDzURwFKCdVHrcDU1VlYb25nn3HcO0pGaf52XGmZ2/rCYRQ49DItAMzdw+q24n/UvxYsKETjUEkLQTUfE4IU1+1S/WQp6cfiL1OSG2Fe5QgiUZc2i6Sz3xyRDHKhUkxej5lPyuyZzMZ9kpRMFqvFQD9PhqviQSAEutUBQ/e+a+rsCMnWd/TXhBySo2ksHW2ymsDG+7irFz3vhGcyeCxPbBEjhbqNSCi5TIss8Q0gPnvsMZwcOawMKR6jA0o+RLVlg5BVvNbQZJykRgkiMQhRCaObkDmWS1kzuIwvndPOu+x+wgNcv4elKL7KTOXpwanG6oxxKKSGsecpAWOZNNAzhNPKMNY8hkrjlCzm1DIgQTtmJzywpwpx7RibQSlnVIkbzSeVl6AuwKMT0pkiGQIHKFFaUnfFIgiIyKAYyqcZVttjFW8yOLYN1nWJebvQwNSKNRpfTJ/G6UNQlFDUfZdRe0ujRhBIFSqtLQggCh+2/4LmUtCHIGzemgEInCNXV0QcWk54eVbgBICPWeRrMCGuWZOafnJjEr5GYRmzMnnXosbbpcaSXiCq/0M0QEHxAZDssQcdFq0mzKMjvpkhab39iqgXRt2TrITBZ2YC+S8qXujBJYbLWxI62UMDSD6iCnxczOrObt9kz2OVdzpt5PVdHRu46yu9VpFKnl2NTl6ecN4oE2X9lqSEGAJx2zVtPGHSNXOEjJSZ3oTqelrqzZ341etq8gK6hSkArpj2lad/JKIkiT/jBLqywSnnCrYeevek7xCdvf3Oey5atflMlPBlVqucT6P8N3rqAnh9jd1FhiliVoWY1r8jQhzcMxNAhg7riX1NwppFL16nfSbyXzxYABEGmlYtqqPguDrkmZ653D3Tn+iyrnLn3I3vO1qASYNMNrYQA1+N0mjAABghAjGfxuSIgt+uz0m1jp7ghMo+kIBlGkB5YZkMLAfgHBUpWppb1hUAJ1IAqXUVMEkdpsQiJ82Gos80PSD3BaUywyHfVLxtchAEhHcIpFhB2DNUpg7Q+xk0MYn5eugwwCSdoo7BfDRImwcic7EYGllYh6LGRKUCQmTxaZOMxsDQCk+tLNhxaz8lmytk/tBNYNzI6T+u76ijglZNSzgEJTiXAhSgyTLFpK/pIeA+EgKIO+nTqYUqaMnbzMllsIACSBydM0E2CNKDwk1ojRoinFZmojbalonxZBWuVhsVl2HACwRlACBM+dA4paEN24k1nxtzteCfWs0nfnkCmRSCF5NfRm7BMaLSZsvu63lPnqKAwjMN2p6CdvAaQ8gWpyCOWSEZxoh9RkN8/pikypLuMZ6GrNpwzh3L/Zd1PPacRgn6FMLxyCuWV1FZIp2Jxpi1YunLmfal/mt9Tk5AzqtKaGeT/R0uzQNFOJZtw0jHahcjJ5020TGsaz0ydLry6XS28hEnNsEeWXeqej75rXZUrgJM8ITXuWDk1YCy9S086to5vQE+QgM+e5v+5KUIsQRtiqAU+bfq6Aykh63R92H0skNRKfljGtXf9j+iLdH0mAhLTGgVEiadNIDYp0TEEC4FnEp99xeE9opZiiACdO9A6YR4maVe8DJDstCt2hlCgUlJENzvNLIW0Bwze6TSlE3CnQAMB3jWvTHrMaCFL6S7gCgQFQ4kQzNE6YzJIHwgxehsndzphnM1yR7rhpDOmVTE1gU55LCrekDmbmdL3k9st5O3nfKhzdpEw7nXet34rJyJvUs8a8IyFSaM7BPeo5PaEFBGB8IBkp6XZrSVOWKOuaTPpICdoA3LHozuRdL/27ZKnGOtMe/YOLRSwyS+ijEJKhn9WzIkMXy3GuQkho8PVyy5Tt9tEVriL1nCtsGBmedSdTBq2kO+/2P11rwvmctCw1BkY5spFhKf+hIJGYaEshmEQSWkVBjlY2b4oUr2YFrZ4TZMpx3+ys35UBRGnJ6AphoyPYmLbOPYPqsvzoJ4SBEkR6VSoFREgJDVOZJLMKpJnempNG0CUVLeY0d5dVHVp0CCDzjPYWJARgUzdgoLpdmRDJ6mTaZ6qet8PgdN01A913EtOVwbqf3VCGZUyRFkdJQZ4VEqYMMsvG9nFn4rCSkuwwx2Jyw22LLUmQ9vVl/YoiI9UTpuQlJkC2HtLCsEMhASmGV34NkRGmxvx0VltNWIpwVvUsbRggoc1WaSdMMnEULZMqOgW8EUougjSoKkUf4VnhIV0FrAWVMRVNu4WDoNVKtV6s0cqeHBqxU05WkCtlbMzmNFIHGJ4jrGw5ztUNbSp1QKm5agSFnZeGFosI3qwQJnKZZ7FnjUhOxqXbc4kypUxvDU918qGP1IOOcAKsf8cUFkup43hgTQ9bpUgGnXkxMdX96ua/SH0GEHtq0MxgsVSrMmlCCGTDhRK7vAsCgfN7l1uu81NLRYV8Mm015pTFK7Y/cBg9O7kZjNiWq9Ccl2hRO8jc0TQz6YQrmPWP2WeTOpXANT44Nbm6M569o6F/N9OaSAtmch3cjlmhJyW4UxAm8WeGqV1uofQn/Y8yLZK6O02NbEhCml6ddXBHn6zQpqRNqb45/SAo4ZpC2DACNxm1FM8RELNSSeZ/NedUeSacwQgYcwki7TvKzBPr3E9MshRNyKUJaVNYzQnj5kmQEzrfd+jX0SgkY5Gik2qx+te4GYQLEjolw+IovnPe+B3xgFrzQUthE7qk2pAwR7pcR7vp95Owwe4dtJ1zJrp5JkbCGML6AzSykppxkUBKS3D9nNvB7Mqk2xYbB4b0Z7crpCSDIV+qLOsfIgGGTDN9l6tz0igBwh390EKM7LeuV6qfBLirNOwMtpRmkmVon4HcrjAVht6ABcxuO10zyf1r4q8gKI1QkGhUre+QxFcZWtonnXax/b8bT6u+uBpZMasJAxEZ0zJdXkrl2n9TkxhIELuht1GclkLanOUEdRozLjWhAXipAFY1Ip5BVazp5yoPo4QsnWDdCqTZ0YbvOGai2yur2AxaBYHNSqp+TsD44DpDJxLypGnZzdIgSgKDWZNRvarrdRAynDotyVPt1wrN4dEUwnKaohmUAL1iYUypBMZ2n5Rff5eTh8BQYRWdyMCiIh3iYWIxrbCCZgLTF2MCfb0zI91OO8HT9QKO7+5rSlHQf5GAN0KKMTpbYISMl0zIpStUbcvGQ2XQGKWa4AormdGknZWleFOXyo60sULJpTUbZ3+nEHNLMuWp9ps+qFVUBdiSZxJhBCQmX1bAJm1IfHK610R2XJQAc1cCLR5O/W/jjxzXhItozIS0KLLDtaHmjutCMb+TU5bqtlpWIalHjsiiLZd+pCUTiUSos1bcwlOYX5p50gUlGRPQrESyp+5JR8iouZV8X8wtIISnySMzv7to36nXUYLJWNqWpcpICTjznWHjzIioU2ABjubmTLiCHtelVmZsY5GG0KoBJqped9IMuIabUqqlf09PJAktqVxUZgYecNwvhgpsO+Y22qKObLu7MMeS9Ei9qlblYq25eJEyLApbwhxVy+vuBPwaEdkFhmdpTaS21SRas/Pdxcq2gduW3o7A01rD9DdlCpCjSBZrNxvUwFoIkR06mDqhh5OkFpQCSqAnqD0dY5eEPDBLCOF30f4JskpmhHAmqdATMaGjRTdmaxEsK2YUOCzfJT7NNL+5PGT/IuF9QzN3VBIrJAn3ScpCyiR1hXCHwNEKJtUndCo9V2B1msvu30RBd+uXZxSR2smjYEnH6o/mqczPBqAkY+TwOgBf7cSRpl8pqagInzBjGrKnO5PUmNWA2Sa6gy8SkxOJlLYRWFrVExEgkRkwd1JwgrqQTAq3DUy6ly58cMfUDJKVbuolcr+nu+eY9YnQSISjKRNWs6YZScVckfBsy5lNXJAz2cgsNyT9N9paktaSojPixqINppQs6DDJkRbGnFJSZOWn1DR2BTPDpbNwnkvKSAF61v3WsUq2CnLGyhGGnIp5S2t0S0/dR1uHoNTWKDOR2Y6F0yJBeiWbrN40JpkJz0jNqRTt0mEYWSWyGEpJCwRtIRhBb5AQIcW/htelGSsHpjBUTJvxcXVTrFma2eg2Tj+X5Y3FfutWfvp3p53avcAQnc91oQ9DhTAZeqhpSLbvXRGWLQ/usCcTqbt2Tj2xRJnCYQJSk7YD5jsNcAgmhLCbcbPPEwDrCMi2wMwNx69iBV5Gk2j2VoPVGROgmdnsreLMPVgwZXwnWWRjGFWNpQ9A6KDQTGPNxY4AMLxqCu7CoN0cyUr7C12nu9raiTq7lScgUptcTfXs+DWt1u7gDU6JjtQE0sSyIjyDSNzP3XiOmRM/pmY+E16R1fysPnS2lWBlITn8BiC1cqZelHq7jGcrzE7qrNBYaoKbSZ28p9wQEuw479UlkaatQUoEhfTdCW5sEFehZNuS/bzYc0u9u6RVohrZBZ0l75gN3bZ+Zgi78V4nNYBZnFA+6yUFlkUjZD4vfi3lOkpMBvNHD7CUyonuarGUmDQCiJCF2AZ2p+pZBPm5CjHRym4kWVaDJNrfKdxApQ6ktzgNFvMFmBUv33lOiUpXIACJ1gWR9qkRbDx8B9JMaGs7wBlaZGgD53s3U18IkSA89z3Xn+IA0+yg2E3ZRklw8rxir04EkL26Mbs1hU3bhA5Z6HjbKQfJ5FDonp0J3qXfGhFaBeP8TRC0i667T2SXvh1+Ii1kFbFMX9LmoUHU5q9tl+WJpIMp5cedbUnKS0J0uiEp+9wSiG2xyzX1FL91p7HnKgoYs5wT/tYDamckA76KRtBBfw6VGCreyjTS9Wt1Y/qU+dSFQKpMh7OlsmstTyQFJe8wQDKtHVPazI1NMYxjJgZMNZx612iiRBjqJzVaUGaDsxkUgHU4GyFn6iDdbwiFumz/Hc1u/RACap+f7rwWzImANIJaOp9VvxlC+R11+RKcmKa23woRqqBT1Q9r1oAsIxhJkVj6nZrTXc0zAocpbQ5KrQUMMkiuLF8kgYYm9Y9BuNnLuARMmUmqke7lM7NNlwNnzIVZKLKKQT9v6JzYflYQ2D4RYLbtmJe7CexsH4hoSQsgi77sX531RBeo258ul0in+bFmsKYDp2nD9n/Npya9jOZD4Uxu236nPR0rg+gyTkSAI9S69TP1myJwKu2TLTORyLb9RkjprehIHCJKGFuERcmzSQewNKRbsmPdH7ITRxjydRGCya7wxZ3K7pVFBkuZEICDMlICJS0oFy0nw6imxKVQgLoRI9HMen9g1zYm5aXDM5ypSp36ymCFxKna2Y7EDF6if7YKOy1sndbE0AgFXZk0+Zx8Eg5vuv0muKtN2bHOXlkeEEIAotPBn33d+KeUAGM77pShkcv/Ng+YK/Ay9Xf7nqInpfObdZv8Ll3StxI6pZVhRhGa72A10bUytnxsZINIXBwpHiVYRGQd85poXduERHEuamLqvgGqCWZx7a+SEUvQhYjgg7Tj1poejr9EV2ngb7crO/BLXuwiCseNmhXaZAYFDpJI3+/Q5Itc3drmAA9HAzuT2SAwuH/NC91LNoiPM28kQjEJaDNOduftzjYCHU59gwDs5HLHxfG3ZU1w2z7LvR3VpSZfyqdo2uKaPoslw3P7wmz3/rEVwEYpsn3WiBtroKcY35SVlC8dgW7q6WSHFKzS5aolq0SYZ4WVGX9K09UKA4U+lJ8oYSDTL9cyoKTaBDsbhJr53fzjsBXM4oZVos5Kon0sBa3Uc8K2Bfa7SxLz3Sw+KduArLmlewRNhsTHSMlCgbTty6pFR8g6HRVAYuq6gn4xpMaZoczwmm9tRRimZu27lnqwFtEeWcL9FVpb6G0hFuYl6jstCxh6T13yo0FFZl6KRSaNaVOyigSnYFsbwMpOVtG4jveLzVJxspJjJ4hmLmMaQwvUFBJKO3SSuk32ha606SKwDHM4cVPQAgA2s4JwrFpSGl0mJlWWJm7fQZ1tSaEfFxzaf/TfLu+pW+zKK6sILN2gVxo5TnKqmYnidXGn2rKc5HVZlWBMzqxCM6jdbnXyVJ+7CPM0KjKmYFI3ACusAFfodppP7liRediSLf1ZOdgdXWO1kP7KSblJe7rMLwY8IxCFWTjSCRytekzmkhkXoqRug4Rcg9a0365+k2VjK/xd9ZYIfneV2Glmxiw2czrVFZe/jDJyLt++qEuPTYNSJsHiwqHb1W3lyXRkMbhvLs/zbBkdJgKnB8+pAHCI9NeaFFZ4OkKmW2R8ahIL/U6W4TMw3ak1EbTcfZCcRy0aEUL7vKxjUselMUA6lYlS/MZpmm7rUqs+i5kyi6Jo9ZCWi5ohu2zVcCecEkwASMfgmPEUymwx2EpqlWqmfmqyZ9pvnOWdJlaG7mZWKWKDKNnS5SKiTtMKAEkj1QEAnkl3ZPgXSPmF1HuZyHe3fU5fzNgbE8n4SRVbZfdbugKuux/NfE+c3GnUY/kSaTCTTHGyTzu5MO1TCZ3NggYnqK+LUu7mtmF2EmG6RBJIVkI5MxZGKOvN/255vmBjzysISE4Y/2LCyg1yXcouNds7WLLVellGzEYOdNMgBq4z0sjKaiDzLyVMYd6zmSeQsDU5zEpsMq6mWqHnnirTrd+US+gumLtdUkpFe+e9tOHl1mwJkdm4ndaSps2OMtJt0O12BnopZOw6NRNKctIWW75ifj2kkNSZQ9JkmrDCVTO4s79a/zEuVVULgRw0kWQUYCDDH13COEynUzQyUe1qQirBwLZDQstVJp0RQ39PIX5DA0dYJoLdTdCXyGk9DwEkyN2dQ8Jm34AV/NACjJ0BNAKRsoPrUiKF5qD5NJ0dxVgoVqFpxc66X2QQJxuh6PB2iuM1ojfvUOLE76ZYsu1MCKX1mRsOk2mvu/BHhriuwAJDpURxx6mb9oQ7QRcXUrpmC/eZu8XmOKVwwpTUhTls3WCLvha9ON10Vpvo0kQF6ZgiZ0CX6I/dxJpudUd7FyvBah0brpdotS7NTzFq9inbL2fydZijSAurbleHLyQjFDoQi/k9Kxi6tN/VqFaJdJgCSRuTWLdEuzrf9CcykMD5mtRhTRCjhBIMYYWWRQimCtLuDisssj1Kmy6AG12fVpypUAXzNgkQxY4i0bxmNiBT52KBpphFYN0OJMkqIbecbiOeHl6D0NPttnrQCkDT906LyLhDPK1yE/9kt96keY2B7v5PR0ilzGP9l5xyfNNTI81is5RsJG66enztZLCNWCT8obNHyEZ3J0Vkgv+W8I8BBrIi1dn0YTVJiEQ3AZQ0ydTpoA9FIEUXTm8O/bo+uvvmbA59wELV9GpiZz8TU0h9l0adE2AyVpj2dGOcJZHgImjRCo6UcEjeN1k93FU3cyVZNpHoaddUNBk1YRz4Tt2MRACBEuGQmeDuZEu3WQuf1FkFBAkJUCpgINXP7BB2CPXUvYQfAaTDa2AUNKeFlVOlaX+2vkTxqN9ExmRa7Oq2f1Bk2tStDabeRKnCCitOnKMwAh+ADQlSfxmdxS5FN1expvucVkKL0983Tnb7Ejsp+wxX2hf1Qy5/aUIlgkHdl6zSGauxI7eA5F0AoFj9LkhlOIyhgxITwUD6vhVrdsIaDeiYT9R9gNXWHOOD6ERqWWIyM8hLGFygu0bsdpFgJN7J5NCIpNeZkkhpKpdBbTtAAKlTYliyjWp2Q06MEnF9AVkflqsxsyuCydDpthn4D4ehnTzpymWQXicSngeybVLrTwpxaVKw1GMkbRiUQaYGmRjR5Qnf0sQnd2ycp1ivXkPqtuhQC5340LKDMFTUPOVocncnQ9onRSl6doxv5ln7m25dcj+b/qiznISCybtg7ni4W/u63e820Tv9ma5r3XxW9VJK6SWmr2N5ptrMVnglgsfSvpuQdRSkiXQXmmeQFjcdZRARfMs8qmeLV4RFJH2XZ5Up5pbTHUGZO2aTJAB4lDwuhLDHEpl+pLSB0+a/RpgkPoHO31JozkJOA2OS96SzarToxclfOxiJW7nzwYx2ybbH8K/LlC5tXf7OMmd24aJDkBsknDYcbLuMj0R0ROITpATiKEQcRZBxCBmbU3p0f00iJE9zotIWej872ZmQOJ8VMzJrjWfyhYFsWUSA8H0I4UN4HjxfwPMEPOGr3PzkwbrHdZUuzyTqoptAohQdVcppdLCuVdIZBePyRNoERup354vaA6h9vCbmi21L0+W4gbVuWX8dwnd5IOmvlFKbt51ozuWrBMzqe0ZvEDrOTPQWmeuKH52xtxKQ7OBYE7eDz9Xlm02tSaFJArkE0yYV2u8GtiJ53D5qKjIM79TQIVjsCg60BuQEQWXKTb1rChSknL3ub9nnOirtLkDt5NaxaC5jA8YNTA7hu1RHpj1st3ek/RWuYMj4vrSGM22xlDNj24GeyH216/W1JrnlFFWbOmAEytmsD0eIJCNqthG2W0C7pZ73PeR8H73VEvp7+tFTLmCgrwfDg0PoH+jj3r4qensrqFRKKBUKKBYLyAUB8rkcfN+D73kQnpqAYRiiHcVohyHCVohavY5arY7aQh0LtTrmag3MzddoemYWc7PzqDVD1JohGq02FpotNJoh2jJCHDNivdVLeAKeEPA8D77vwxOeEjIEgFjvCSSHhE4YDNQ8yG4677a6ar4vZsK4qKQr5Qkq3YujG5XgcoJtVaEddVkjwx1j3SbXPeAKWIP8TIXCyfBqeG0pJOdeBtWSI0PYaWsH0qJEISQJfrvTijLC2Vy+2cZhsBjDs8dsGahnooTV5UZ32NeslLUazIIUvTSp/0LGYCH0Dv1kud+eq2cmuJ6YTNqHYQSo0/kEyHBqQFOXNi3c9pl/3HpsZlX9Vy2KOcdp2XqM6WHIm+hswGhbdY85eY4y+YMMJU17OiaBEO5ebotCtAp2utfdb7XYxZymkdB9jYUSV3FIaEZthGELiELA81AsFbB2xRDWrVqGrRvX8I4tG7F8ZADDI71YPjKCSrmIXC5Q4xQzWmGIRrOFdhgjbLcRRyGiSCKOY8SRVpFCTRYhBIq5AkARPEHwPR+5XICcHygBl88jXwhAQhlwUjKiSCKKJer1JqZn5zA+OYXJ6VlMTM5ibHwSXx0fpbHJGczM1TA9s4DpuQXU6yGiKFbpgIggPA+B78EPAghP6KPBPKTCJmQaoSU0767sXFMSzDYpHmCEk+Mgz5YhHKVOUL496QhRjUZTm6KJUwqfgEVRXvY3IpN+SG3kJpVMTo0NGSXZ2U8XtSd16awXxlRPpL5dgLH8a/oCNectnkgIk2CRjI+YmUHF4S2288p+FlZgqfzSymGZJFCTAHnW/je+q86jtHUbJOtMiBqhsExMUALgqY6aSHvHctAjQE6vEqJZIiBhlqy5ZPwBrNtnbHFzFLt7uYkAE9Mxky8IDCItfK3Q6hRYYB1BLJIj67PpUVTxqkFJWmSDaDVjm9TLnGgmaO0LopS57PZmKZNeOOjXHHvfaodoNpsAYpSLeSwfHsLmTeuxZeM63r5lI9avXYFVywdQLBZQrzcxNj6BickpjI5O4ejR4xg9NUGTM7OYm69hvt5AbaGORitEFEq0IRFp20yazHc6xEMIk0ECGv0oxg98D54QCAIf+XwO5WIOxXwO5WIB1VIRPdUyhgb6eHCgDwN9FVR7yuirltHf14NqpYwg8OyxaI1mG+NT0xibnsPY2CROjk7g5OgEjU/MYGJ2HpNTs5ivt9AKJSKWIF/A9wP4fg5C+PB9z1n1ZIfYKYor1jHbhPQ4mpU086jh+8XQmPtdCGFPrbECi7qIEC2AXd9Xp9sgfWXrN75EE8RqutjNtKPkxY4yTbnWV5ztp26/NW1leoWxm5slWwaVtMDSbku7c9wWBiDtCdNS2InfIovC0p0xmoaIrMCysgBInOtSuqA0RbzkzEDHqHI6mfpNU9TqNIIVWKpO7RjtkjZGGmZwUse6z5lVE5E69cbMNvXHohdOepL247kNTgCjcVS7BrDdxM3acOQ0UxiFZVbpDN1TS9WsXN924d9T5bbbMZqNJlCvQ+Q9rFg2hF2nbcY5p2/n03duQ29PBUE+j6mZWZw4cQoHDx3B518eo9GxCRjk0gwjNUrGxBDqfyId/CvIpm8xgshMrOQcvoQyrM1R9buiRQwJlqx8Y5LBUkLKWAtq1mUr4ZbP+SiXCuiplDHYU8ZAXwUrlg1i5fIBHh7sw8jwEIaGhlCtFBEEHjxPoNluY2pqFhNTcxgbn8TBr47h+KkpOjkxjdHJOcw12mi1lakphAfh+fB8HznPV6mO1b4T1XpjjWg7rZtQSokbcnhWjx0BqRgsyryfLU/NLXc1UNGErILTvJLIzJR56Zbnql4rQFKmpi7fyf5pykvzpd6hoQWUfcbpPxktxZ1+OVtdF6GrBNbQFiejgYNOLDOZIMqMMw6ZYLekXyBPOcu7nfLtSmHj1OTMDnd1LDZDCoIHgpBATJ2dSnXEQSVaTun2JMeWG7SSTWasEJjOPODQwBWSWcif2OUJxFS8KlL97qpNOQmKNMLYmKRZk4EN49lsGFrSGZFJ6iG2X5yOAfDIA0OgFbbRbDUAGWGwp4odm9fh3DN38JZN69Hf34vZhXkcPHQE+w8cpn0HD+PU+BSm52qI2wCED+Q9eEGAIPAR+L6OxHcOhE351hzT1khy2y90thUASep0clukrDtkBotgj5BT3hOBWEpIqczOUIYIoxCsBR1JiZwvUC4VUCnlUK0UsXrFMqxduQzLRwZ51bJBLB/uR0+1jGKpCMmEWr2J+fkFnBidwOFjYzg+NkVHRicwOjGD+VoD7XaEKFb1e76PIPDheUL55jTvxEjziiuQzBi7W1GI00LCCi33RCf33cwCi6G7QVsCBBakt3h1Kv+U8Eqmsi4nsTqSee6OSSJU3WMAjRsHGashi9YWE1RuX9x67PwrDW3JBGupzloR1EXqdHHHJA22lOj6qvOwWgpnKeHIBWW2gFSOaqFWUYRUOau7dSK7umelt/4ecZykZdGN68jPSUkQ4WL+CQA233fqGSvZjSNedOTzdttty0RicSZWRpfQCTsWib8gK9Tsc7r9Jg6qHbbQDiV8j7BmxRDOPH0rztx1Gq8YHECr1caXh4/i471f0L59hzA2MYd2S/msvJzy7Sj/jjFr0y1jkI2WdumUpDAxpoqDb01a3SxpWI1K528JfZKfM5qXEj+HGiaGEOnJyAzEUvlsZBwrX5ZUrgkBRiHno1jIo1rMYflQH5YP9WP5cB+vWbkMK0cGUC0XUCyWAAC1eg3jsws4emIMp8ancWJskk6OTmB2oY35Wh3tSKoIeghFS8+DH/jwPR8KlCU+LhIiQcVQ23OI3NOaKPXXXF0VN+n9A+ykH3KOqxEZnjQo3GhyaeZNZjw1WknmBqdXQ1VPHTRlxyU9ltl2f5252uHaMffLQ1ustjcaP+uXsoxjfEUZgZUgB9gQBXI9xos1TBMg64NKbKUERhpN1L2bDmEISRkaqXFSAOy5fNmXtHnqKHF7ubnRTdsZSf4Fg+jUM57uR6a/KcRKmQnvENryiHqBHQ2QQn7OCcMggmAJFh4kA2GzjkAAQ8MD2LVtE7ZvXM99fb2YnJ3Hvi+/or1fHMTJ8Rm02hEQCORyAQI/gCe0UWbr1j102pPQiMDe0oGzgijZxJ653L4oFKHp46IGN05KjwuTEW3GhNT8RsoklZJBLO1iiafbKMjTvJGsiqkFMoE4lpCSLUKL4wjQG67zgUAp72Oor4pl/VWsWj6EtSuHuL+vF30DvQgCD3EUotWMMTYxhbHJWUzOztPo+CRmFppYqDUxW2shjFUnhacc+77vgYTQLlot2FltYzOZEihFc4dPYLCFztbLBE/3Ty0wOYtZWhW4Pm/AmQJ6vhgzLoWS3RqNQERmDopkvx8jQYWMREiSLszcN+3vpni7CefUfePDAhLzw9Odi4x0NveXElhmQrpIKCOvOmJIHCehW1a3mKi/SmA5HTZlStMBacIF1MCn5KIZYHQSLBX3ZScZUr/ZIEGhzBM10OnOmyT8TLZSSO5EdO7SshEM2Su5B4erGDJqo5T3sXr5MLZu3oRKtYqpqSkcOHQUX52YQK3ZAoRALl9GLudDmBxd5tQWNgpXwuyrMgKVTIddTu+a7C1hczsBHMXjPuvGBSVH0LsCq5MuEMIKKpKMSAJhGCOKQwCMYqGgEFGhAAgPtUYLkZTa3WYCZzPZPjTaId1Jm4aFGbGUiGWMsB2CWSKOIhAYeV+gr1rEUH8VK5cNYf2qYR4ZGsDwYC/KxRwCXwUnL9RbGJ+ex8T0HI6dnKCp2Qam5+YxvdBAI4oRtRgqMQorV6An7OESPpE24wC2AbGcKDVDLTNcANhTJiqB4Rk/tMETBoWbbpPmL4f3U2aa6x9FInwMmiVCR/iB+9kVWKqtJgwCdi7/NSZh6l5pZGsisPTflMBiRsdeQE4QhemYlZ6u5DRCzCIBzRC6k91sWNcnop52BFaXa7HOJTFV6n0pzUB1rkQIITpgeNdAS0rJB5t/SB3NlKSlsayk+2uEM+n2JH68ZFuNKd81d23/HYHBzDYEJNkbx2CSGBnowYrhIbSiCKNjUzg1Po0wlsjl88jncxC+AOBBSnPIQtyRdUKNlQm85ERJmPFOaeA0wkranWhR2/Cs0NLzxNLMOaZeV6dMlThGpFFPGEUK/UQRICWCXA691TIG+nsw0N+H3t4eSBmh1ZaYnJ7FzHwN7YiVf9KcZ6k7k17IMSunqn+SGVEYIZYxJBOYJQQBvgB8TySogmOA1cKAD0IhH6CnkkNvpYiBvipWLx/mwYF+DPT3oFotwQNBxoxas4XZhRoWmi1MzsxhYmqG5hdamK+1sVBrot2WiBmQakORQpUisAvmQhB8z4MnJDxPLTgEvg9PCNRbbcwsNAD4EKz4moWrPJJDWdms/C+iULJzK2Wac7LrooNnjTByZITUM8fupUTGl+yUsRhiB6B9WM7u6a4POY0EAJGJYVCSHbBpZc3pwgRAqn1jKqWIzmukobuZoBadZVBOVnKDkngo96SYlEnqROyqe8KdY937l0FYKQHiYCWz740gABYQEJAU29VMSAaY1B9mSKhjqmJrYhkUwwlKYhMuYqV7pnHO3kM7kC46AMASgiLk83k0FmpAGAGBD8rnIXRoRRJfI1S4BBHMKd7k+C7IMC87Y+PSxi6mEOA5TlzdZ1IksMkGXS5nO85K0BufovogNf3MDQI8gSDwUC0XUK0WMdBTxnB/FSuXj2Cgr4eLQQ7C9zE2OY3RiWn66thJnJqYRq3RAkDwPHWStjl4VA1osprJ0HFdYYx2O0QUhvCFRKVUQF+1gOHBPqwYGcJwfy+rANkS+noqKBfzKBYKCDxPrThqfo61SRlFkSovisGQAMc2mlzqVNkWO5MSwu1WhDCM0W5HaLdjhLFEO44QSbVs5EPA03Ld94TG8TFiJrQjiVa7CWLGXD3GS+9/QbU4B9/zjdRIsVT2FGnL/1k01UVgZRW5zp2r77NdDOl418iOTJzYYle2fnP5piLNOh1iy+QzT5abuxWODqIYblVMLwFWKxbsOXElS1zZsAWhJ5G7jcigulTktzP5E0cs7Heb+tY1TYlSzTHzTFCCmkzYh2RAhhGkDCHjGLGuTs1/1gzlw/cD5PSE830P+VxerbAFOeRyOeRzAfIBIecHCHLqN7XcTioS3A/UhNNtS5CnGhPld1GTIwxDNNshWu0WYh1YGYZqy0wkpfotVjoukrHNDy5jCQmhtHks7bmQbLbHINHAxlGsuTalIRNTS6XRETqKnYSA8FVwqIk6D4IAOc9DQfe5WCygUimhWimhUinxQH8feipllEpFlAp55HIBfKGCG2v1Bk6MTeDE6Dj2Hx6lg0eOYWx8BnMLDUgGPE3LICgi4QJoFwZb4dVqx2i2WiCOUcr5WDvSj9UrRrB5/UpetawHI4ODKOZ8CI7QjiI02xGarRCNZoixU5OYq9cRRhHCdowwjCmKGTHMpvTEH2b2S0oZWblPDLWVyBcIggB530MgiEn56OEHHnKeB49UQAoY4FiiEcZohxGa7YgarTaazTYWGi0sNEMs1BbQUxS48MxdPDk5Tq0wAgV5QOjkj0gj46wwsRie0/fsCXxmrhlzmV2ElZRtIgf+WjOvq/nZxVR0hZcPgoqRsjAqUxFgCWcue46cSwiNHFQAaLI/jIBk47FAskRLupHsCA5d4ZKS17RRSb3E2e2Q2bROLXs72wYMgXSzBRnsAZ0bSZUXs0QURYjjFjgKdX1KkBTyAfp7y+jtKaO3p4qRoQH09/agp1rhnkoJpVIepVIJxWIB+VwA3xPwBKnJa/4320ZI7YMTngdBakJ7noDn+TqokqwJYL4LIg2SRPIMkdljDRhEaMxwAKnwA0HwSIdvQCFQ63MwaEQoZCI0Awnh5HEygstMJvuzDmIlQOrAH8kEtTlZZ8cyzC4ZURQjjEK0Wi2022006xEWGg1Mzc7j5PgYvjhwEmNjs3RqfBKnJqYxOT2P2YU66u228tkID/l8Abl8gHJvH2z4BFvsopzWGknGkjBfqyMOm1g+UMEFOzZh92kbed3aVeirlhG1aphbaODI6BTe//RLGp+ax8TULObmami1I4QxI4rVoXQmdbD1uwnjazIhNQ4KcecBSFkhUIsyQhA8NbbkeclY+p4OAtBzQ0qF1qVki86ZGRxLsOdBRA2cccFORFGEfUfHAFGAIAFf77SQFmUZVZysphsdlBUScI1EF+3o8bYAAo7DHc5cVBofrk/WvQy4NqAja21Z+mXa5VvRoyvvArFMmx34qKVxYiyqim1nlFCTrBGp0GEKpOEoWwykY2/YdiCLvKw0dlBTYk+bg6+MtlemRQwTbEm6vMQkM+8KT1hzMZQSUauJOAwhBFDI5TDUW8bQQA+GB/owNNCH4aEB7u/tQalYRKGQRxAEkJBoh6HSvo0mmu0Qs+N1NBqj1Gy2EMcS7XaIZrOFRrONZlv9FspIL60r7cnQGtnBuKxpYukCY74RhFBamkibPSTga2HoeQJCGMFHyOdyCIIAvucj8ARygdLsfhDA930O9BYVz/fh6yV4TwgrEIWnPnua+cxkiaWicxypdMfKFArRbLdRb7TQaLSo3myh3QoRttXvrShGq91GK4w0IgzRbIZotFpohSGiMEaymkuA8ODn1BYd3/eRKxZRKJUcQaAFh/Y1uQs1TFA7CUig0Wigp+Dj7DM34+ydm3nl8gHUGw3sP3yK3v34eYyOT2N6dgGNUCIGLB09z4MvcvAKBeRBKJCDSLLbRrS7wCyuGNO4K5rQ72c4HWZ12SBpoeMzVHyqE3TNDMkSkpXQLwYBRoZ6+NDhozTdAHLFIiRFepU1QcLG4kiyZRhSm9VW9WNCR2c+GonkpBS3lpWeY6THQGTKNfwLpzwiDRIsj4uE+x0A0oG0SiNbk1U/StpnLrazxrlEIkVtCIRHNj+SB7Psrx3ExIgF1AqPNinM9hWQCgqFYTIke4zchpqBSgQY4Dp91Sdt0pABAla1JR0WAjFrk6ndghACvT0VrF41jLWrV2H1ymUYGRriUjGPnOej2W5jdn4BM7OzNDWzgKnpeUxOz2Ch0cB8vYFmo46wHSKMJFhCaWB7xDQlCFLv5km2PqjVWFfr6ZmQVgTUOSh2OIymRbIKabRe8hzBPZmmYyzJDDKsALCZF22bCOoM8WwrsnCcAIjkHYP8VAt13JFQsTseQQhPpfARSriaiHgrdoRaaZPGt2Xr0B+dgEo3XEUAiEGIwSh4wK4t63H2zg3cDkPs++oo7f3qBE5OzgFxjCAI1KqaFtheF0GS5UUXSRmfTKzVjWcQa+Lhz7wLB7FYU8E+n7g4khU1hoPmDPX12EsiUFjDBdtXYdnIID/75ucUe1WwYEDG8PTqtfOiClfKTnRKZz4VROpQUyPYtN/DdV/bhQpSLCPgpn/W40NkgYp9R/dV2qh5Q2l0ZFvtWJQrDW9NiJYepwT5dGFyo23dkzhMKXaLhR4gydJueSEdIGLNNF2eNF+oszVky0mgrZmMBl7by0FvZsWLhAcJgbAdImo3USwGWLF8EFs2rcWmdWu4r6cHMRjTM3M0Nj6F8fEpjE9MYWpuAY1mC612jCjWpZpNu55QGQCEQjjG1+QynrFS1LiKRNvY1TdyG6yaT8nRUJadtTqz3TSaya7IGShrnOBGuyXENDF2CeUc+pt2OTSEYTjuvi8tURhsGddMYrc8sxKVvG3abg45MVhZLdlbRzySCGrDA+rS+do0HzhYwOk3IGWMUiGHdSuGEAjG/mNjmJipgYIcSvk8cr4+lIIMmuUOmpgNva7Wd90PyUqjWnHznKBhF2F1TDpHMHTz7QBpYQgoBJeKVwRAzIgAeMRAq4YLz9iG3kqBX3x7D7WDKggeBMmkD7of2XYY31QinMxjGlSYBSIgWXF0qe8gskTV6ueEM5a6TMfogUFiRtAoCyLh7y4CaxsWu1wCLXa5h0daAmgzzzSIoRFGt03HjkQ3tWR9+0YqK14mcCocgM38Ve9Kx98CIJYSrXaIwAdWrxjClo1rsXr5MuTzBZ6anaNjx0/h6NGTmJidR7PVtJNceD58L6dMImEEkmZok3qZyC5KLE5DJco7/HKOQDKaRVUsEBvkRM6kdbjJLgS446MLShYJOvWMuRbLTJq0ufNAza7POTE1Sbuyz7hd7rxvJn2Coo3W7TaRDfozAkvA5Sj1KiMWAsSMou8jjEPUGk34vsr8kJhVCULopiA72plCP2lBxDDbXuC4RRaP7UsJosUUgmuaOcjGtsOckwCG0Cus3K7j6kvO4JBBL767F0GuBywj60tyZESqXuNSsWMB2LlGzju6AR306BAqeg4RJVaTeicxcY3pyMlgdBXsHWOwmMByByarDcxvhrET4qUrMs9A+1zY7Fl17mc7D3RjcrYHHECogEunpVZgKW1hzAjlOK+Ui9i4bhXWr10FQOL46CmMnprA6Ngkmo0I8D0EuQA5P58cy07WiOl0FqbaDLATKdt1wmZ9F6bvBMQOQiXTPyiExUCy0dR51w3XcMu3CyFkJVeHwDKK5a8RRt36knnCxpQthSCyY5nlpyxvuZk0sojDjDXBbBdKzDMQEmSq3ROQrPgFySRJJJY6GivFi2a3Q6bexfqY/W4mfhJ3mB53d4K7SmMxlKW7pRBjVmCZcvQgxzo1TBDW8a2br+SX3/6ITkw1kPMDJ/sVLKplpPkgHeqgmm7nuSCbVMp9bjG6JP5wSuIg9T0PBOFaEIsoh0XpkRVYKnmdQkOQDHO8kfty16BK874zwCoWiSF0sB0x22OrbDlkJh+nJlgW2aUZxxA6nV7F2PpSqiXijatXYGhwALV6A8dPjmF8agrtiOF5PnJ5LaBYH2vOAkwSzDEEBQA8mH1waSSjjV8zcOz4nKzGZctpWeInJhMhNpAbnD46yggbA6GRpnv26qrpNKO435mlDnLVjATS2z8yQhmdExeZJ0zh3YRf1tdoyWMO4qDY1mknpNmVxmobDZF9W6FFI5UoEVJuJLzZWuJBTa6k6WTpaGilvmnTxKKIhF6235z4jlwBJBhJMDVZw75z4/Ii9HPnh2v+ZDODugIvRrJB3ijxLDYk4SFs1rF13TJIBg4cHUNQKNmzLZFpj3ukL8HcT1wG1i1K1kugBXPy14Q5pMCM0wfbJ2PuGXp3QWhGMBuLCno8U2xcGt6WsietwJJaYGV9reiEq4vdM50VQqgEcTGndm0bgfZ1Wlo/7RDV6Aw2t6zWABE8ITDY348oamNiagbtKIafy8H3A7U6Y53QJmgTYPiQaEMQgyjQZoc7NWHrVO8YEI0OxmGDCjUTphCnLk/lGRNW9JrEvqYWyUk3uyEOl4bmXlpgQQspR+hrgW4FFgkI5rRTHgCE6DIdnEsz1GKTMsWErhAwaNTRWmaKqP2nHsDQm4AJ7DwnhVZsrCcKEp+ZhGJ0Twh4MKmJHEGTanrGoZvM0bTwdfuYPJLU7Qon8zyQKrsbmswqsG6/W6e45mvhtCE1Kh2kJ5BkBJ5EoZDHfK0N8n2NSjtRC0lTdjpwlJxn7NyyBxdqoY1ElWb7ZLK/uOa+h85+d7sMIrPPKelnF1jsqTmdL3YI5K5QbbFAMXtPpwlG3G1XnOp0N59KJ5rINsgMomMzabQjAExOTqIVMbwgh2JOt4VjkPY/Gb3i4jONkzvawM53RWxh33e9A0mbO00e810BB5f1dP3urPj/4eoYAwPL008lwk+3t/uE6hznLhX+VW0xWCDFZI4ZbRZybRAq0iNjykuElG4/p+918GqmHdZXkr06tLGp3FgaSLW+G1KRjmnfze+7lLDqdnmkA57t2GjEk0HDFm25qNETiCBQa0n4vu9krk3ek1Jqn6xeVCDAHPJiKzRGgjs1dH12xU/zbbZ/PlyUkwjExWSGSy+7qJyluW6Ib7fLIP0QgESqmonbZcAXNxsMdRhCGNODUpPoa99126JPjnHbSdqkVBo6WbEJNTwJAgLD7NzXqeyYAGMGGj2htxR55KugRAcaZzqr6aCZiJAcddXlytLVPSxURV0Z4akipWFRiGYiTuO7FD2ySJbZEajpieoyopnIZgXVLmcBFlm5bbfPdsg+7QvJ9N19T+qtSiTSMD1pH+s9W4ohLd1J42WSIKhTrj3yUr5SJ4oDLJLFidhpc8cYkDZJjAnDSNNMJuZQFhUb94EZEnYmriecU3q+BgV3W9DIjhlB8WhigqXHJHnOPKvLhtp/aDI0GAoxp/lF3U94nIEkX5bpt5FY5AZnZ47Nc5qTalv27EGjqM1tx+ow9OkQYA4tjMAGkdqas9i11EpSt2e7mXXmnpnkqXe0yfm1yCIzeZaYxmbqpzptCA7KTAx0tmkperhDrBg3wQ9wtYxGDeQOjF6W1lyoEAMZw8uYmUaTJBpTcpIvbOkFgC5mtW6vQbqm26ly3LKdMiytM0jBPmtgumNWu+3KolPqKANOeySYnSAG68Nx+GoRJK98I4svIih+0YiW0iuzpm0mot8Ic8oKFECnXNZBzjpoVxj6w/iWXGVAuv1uH9z7SDFf2pfDSXsW6Vc3a8d+1nxGpFcTRVYgQo/f4gtGQiSJKCUhPeccAfR1Jm63dnbwqUiEsi3HKAZdn6GVvwg9lry6MY5LXJuXXRPK5JNSzyWaWXWwsyR3b6OFxamjv9XFqUFQaCrdouQeIRFWbH1gS7GEUw+SSW6O7VICQNgipJQqhW+scoPHsdrFbwpgi5h0G4kA8gxHOzNY2CYJj0Dkqch1d2sPJVNOmrAJIyCIkE3VYmVr16uTkc1E66CDQRuOMoBOOmcFlBG8+omsNk0qU0hKasiSygjiTlxTN2VGygg7pzYjcBIhS/Zl4wfySCjETzogFYxI6owQeuuLAEHGRvGJlEBLWIa0QjECzew9NVutSO860PVlMuFKTaxup6Lb+aPrtQpiEUBg6GMVsxGWdhSSy+wsMfR1FV22/GSGqLxdWQS/2OJbV+WZqWMxgWvqhTC+Qg0J9CO+W7F5mTnDHF2ubONtcHQXJGUaIYDEjDNM72oWVgzCFCdlmnes1k1ksSu+VLGOxoApk1LaDYz0Sb3WL+DqXCSMoi9BBAgBCagkb+02ojAEYgkItXWlkM+jXC6gUiqgp1pGT6WCUqmAUjGPYiGPXD5ALpdDLhdwLggQeD6IBOI4RrPZQK3RonpD7a+br9UxOzuL+fl5LCzUUGu0UG+GaLdVcjlAgIIccoWCPpsv0O2OddZJa+Gkcz8tddkB7LLy5wolMj6WxRkzGYfOssiGPsdg8oAuoSHJIor6nygJqNUPKpnPQPZId9ICxfOMKaqUoIxjtFstrVhixCyRy/ko5n30VfLoLZXQX6mgWi2jXMqjWMyhXMpxMa+2N6nsqwDLGKHeZtRsttBst6nWitBottFohKg3Wqg32mi01JakRlsi0qgrIAE/SBRQosgd7nPgjNSmWdcgWnZjExM6gZJsGR0LQppWhmakzdlu2YGVQEtoqOpNQsQ73AaLIMZuAix7WRMd7OS+M/NWAxJm+N1jYhLqUWbidpOqzCbcHwCTynjIbGNSYG4ZqMxaS5uo2RSxOk0QAbJxHIt3WNWSgtaOpk29a+CmYw45qDOB9rofYRii3Q7BEsj5AXqqJQwNVDEyMojlwwMYHuzn4aFB9PX2oFqpoFQMUCopIVXIB8jncwj8PDzPZMA0Gq6jP2r7GwlIZoQ6TUm93sTcQh0TU7M4OXoKk1NzODU+TUeOjWJ8cg7jU3OYqc9DMiPwc8jlVeoTgVjvUdRMwM7AurRzUS1Rt3ZZE0cTTD+7dAyaBYLZTqa+JCtx6foclOH86pqI0BMO+lxKtTFcodIoitFoNNCO2iAA5VIRg/1VjPT3YO2KEawc7uflg1UMDfZjsK9HCah8gHzOh0qUJxHFkdrfqJGXlGpFNWZTH0yOKhZQAb9Sss7w0EK90dLjNo/xqRlMzCzQ6OQcJqcXsNCM0WiGiPSpUkGgTuhRZpzxsVqo1YWnE7oTqW1I7v2lkEw29GgxtNMZsuKY1sbiyOyp7GYSur8t5TZKrBekhBXcstTWnIRF7HTSytaNwzIFe57XQTirFCj5Yg8KcDtgik5pA7NKRCAmxCStdlDJ03SgYEZ4ZoVplljKhCGrGZNGuu/AHqqpJo5AHEk0Wy1IlijkfQz0VbBy+TC2bFyHtSuX8fJlw+ipllDMB2oPnBDIBT58P3FlttoR5hfqqC00MTu7gFNT05icnqVavYlavYF6s4l2pNLDGEesJ9QRV5VSAT3lEvp6qhgZ7ufly4YxNNCP4aF+DA30oVQuwPN9tNoxpmcXcPzEKPYdPIHP9x2gz/YfwsHj45ieWwA4RpArIp8vwDj4WQ8u6yheo7mE0bQAQJ6ln2Uqg7D0kW1A1kRxYIExrBYxNQhsA10l1KKH3QtJEhZfUXJMWkqxaSILUvvkVIiIyjzarrdAHmOgp4g1I33YvH4Vtm5azxvXrsD6FSMY6CkhFyj+rTeUEpicmcPUzDzGJqYxNjGN2fk6LTTaqDfaapzCUOWDt6mydaocX6UOCoIA+cBDuZhHqRCgWs7zQF8PeqsFlIoF9FRKKBZyIABhGGGh0cTEbB1jkws4MTZDJ06pbBRzjQhNych7PnJBoIKtHT9ZlsbS7OntInC6KxADAHSJroWUecedS91CZ8i0iRJFthTatoLL6cGiyMu0s1sfsoGjpO0wYxbafdFOwz3PQxzHqd8Xk9KL2blGYLkbno3AkiRTq0CeEOCOgw+7Xx11k+hwotrJagmmoufb7RAyClGtlLFuzQps37wamzat5xXLBtBbKSHwPXCsIugJgO978HwPYRxhbGIGx0bHcezEKRo9OYnxqRmMT02j1myj2Qq189NXk5BM2jNpJx9rM09Jc5X0TXcIvi9QyOfQ21PByPAAlg32Yt2aFbxlwxpsWLsc69euRH9fLzzhYW6uhgOHT2LP/q/w3kef06d7v8Th42NoRUCuUEAhr1ZbTdS7qd/dTmUCeR2q6hVENkFCWrh3OY3E+OLI68obqjQzvgRzwJuN6yFNCyJApBWjIIA4BrOA8AMwCzTbDTQbLeS9AKuX9eO0LStx5mmbePf2TVi/ahg91SIkS4xPzODw0RM4dHwMXx09RaOTczg1MYOp2XnUm220whgRq7MTiZTPyyMVJqBiCT2LAOxpT0CiAKyGTxB74BECAVTyPvqqRQz0VBQiH+rh4f4KBvuryAU+2u0IM7M1nJycx6GTE3T01CymZuZRb0UgL4cgyMMTSJ0ulVL6Gb7P0ts9oYaI0huRnXcWM+m6lWtDTJwF4EUVVKbsROg5qH2Rtnf4vrpFuutH4S5np6Cbk+K4G1HsihPSEDZFECuw2C4Rk45SlUJ2ECF7qOliV4fEdk4OMf2CDuWQUurMkG0UAw8b16/GrtO2Ysf2Tbx8ZAiBr/oUR23EcQwioFQsIcjlUW+0MTo2hi8OHqU9X3yFI0dPYnq2jigGAAlhT0rRqV7IDFzC7MlRSOqfxMdGMI2WJCBZtTWWkTJTdIpg32P0lItYvmwIWzauxu7tm3nXtvXYsnEtBvr7AAkcPXkS73z0GV57+2N6/+N9OHx0FEyEYk8vPN9PzoRcRLuaBjIZlGoElkJK7pWskqrwkQ6TwqJmkwBIgHUskGd2EIDAUqFiCQaM8NJjScIDohj1hXn4Alg5Moizd23Ceadv5p1b12L1ymUgEpidXcDBIyew98Bx7PnyCB08chynpubQCBkyVlYCeQrFCN9TOccoCQq18UDcOWkSE0XH4xHrDKCs269NSKi0OyyBOJaIOQYRIyCBajHA8EAF61YNY92KQV4x3IPechk5v4CFxgJOTkzjwLEJOnBsCqemFtCMGb4fIPB9JR7tflbTju78300oCU7vJ13Kx2R4wc5vrdiMwHIWtZ2yYH80/ADnMeMby8auaW1l+STbByICFYeUSSi08uzYeJxIjsTp04Uw5ko5/8yzcKQwW55XUdeclidEaqNnBzLLCKwsVF30MhMIDqEg0W62EYVtLBsZxGmnbcLu7Rt5/bo1yAc+mo0awrCFwFPO1lzgo1gsIgwjHDp6HO/v2U+f7T+MsbE5NMMI5AkEQQ6e57s0VxH1Fs0JPXDJ1gUJCbPt1CwaGOZT25nMFE6ISyBIYcw71jm32oiiEDKWKOUDrFvWi9N3bsJ5Z+7ks04/DatXLQN5AkdPjOP1tz/FC6++Te9+vB9zCy3kS2Xk83kA0smGkRZW6hJQCXEFVHxU3JXWbDSvYxKqU8UB5SRWa7lKoKkTZJS/k+HKP7X4YtCWAISHVthGa6GG/lIe5+zahCsu3M0XnrsTK0YGEEURjp0Yx3sffYH39uynfQeP4tTEPOptBoJA5QXzA3i+B2EY0qay0al9nd6ChF60iNWxYaT6BIZSPtmVKTJpcNQXrW5AJJwV5WRSMkONmZTwBNBfzmG4r4h1q4exYcUgDw/0oJj3sdBo48TYLPYdnaCDRycwOd8CC4F8zoOAjxiR5gUnYwgcIcQqi0RqPiyCnpYyIxdDcK6PyvqzNHIi0hjcyAO2ASbJe657xrTPfk/S1aQRloOkknxN+rvTsO4ObacTDDWazvOqjISNoQUWEwChcu5kvO5Jzh1y5Gw3hGXRCNKNdgjABtXojjeaTXiIsWnDGpx5xmnYvnkdjwz2oR22cOz4MTTrTQz0DaBSLqFYCpAvlDEz28C+z7/E2+/voS+PjaEZR/CCPHw/D18jjSTWBxqNCHAcox221YEGHAOx3kNHauWOPAGPfJ3h07MDy0yIdI5waewOQfBJ+bl8Xx0TZaEaJQSII4lWq4kwbMLzPSwf6sXZOzbhsvPO4HPP2YnV61aiUYvwyd6DeOalt+jZl9/C8dEJBOUeFApFQEZaSnZTAj5U8v4IQNzJC0SATvxnMiqoW9onScp3JqEnmFD7BwFAcDZ1tRpBKTy0mk20mvNYNdiDay4+G9decT7v2r4BpUKA0YkpvPHup3j17U/po8+PYGx6AW2WyOXyyAcFBB4BpFJ0m+yqzCqrbCwZsVSOcqlXSEkAvvDgCVL+SZg4LxUIG0WxSj2vZ4YghSR9n+H5geqTUM8LaUxnWKGlPutJaDK5str/GsUhpFQJ+Yb7S9i4uh+bVw/ycG8Fwg8wOd/CgeNTtPfgKEYn5wAWyBcKMOEhCTJP4gE9kE3d49LXzpElBJH5u5jDfLH87CmB5Wpcg1bJPpV+twvI8QCdBFQLw6zAAhskopnRCLBFBFZSWdIguy/JBKlk3iOdSdGYgh0O/DTkMvYTOi/H9HRIwE7fSTsuw1YTviBs3bIZF513Jm/ZsAKVoodGo4UPP/kc+w9+RatXruTtW7egv7+KfDHA+KkJvP7WR/T+J/txamoWnp9XDmxPbc61GzO1T0pKRhiqzJpCEHI+oa+ngr6eKvp6SxgZGsDy4SHuq5ZRLhdQLAcqzW+Q0zncFV2iMEa92Uaz0cJCvYnxyRkcOz5KYxMzmJqZw9jkFGq1BqJQwvMD5HVog09JNJraBM5otyO0mg34HGHtqhFcddm5uPm6S3nrxjXw/ADHTk7g6effwB8ee46Ojs8iXyijkM9BxpEVwnaAyVNmO8UwR7S7vKAksafNRS8zTs6+QI1uhOtURxJES0QQno9WFKOxMIfVw1Xcft2lfOM3LsbGtcvgIcaefYfw2Ivv4eW3PqFDR0cRskChWEIhlwNRBMkEQQFIMCRHiKMYYStEHIXwPIFiMY+B3ir6eysYGezB8uEh7u/rQW+1jEq5gHzgI+dBpfuRyrRrt0LU6w006k0s1FqYqzUwNjVD0zPzmK+1MFero9ZqIwIB5MP3VBiLyg6L1DmDdk5ppUPkaT2hFFU7bCGO2igHHlaNDGL7+hHesGYQpYKHepNxdHQOnxwZpRMnpwGRQ+AFYJKQxHaHqhKWWmB2EVTdfM8uYurwHznPqlU9JQizPjLXN5XMZWO+JuFMcJCW0MLWBPqa14R2odj57JqE3S43n022s66ElaR3sUuG9PTBjHEGepKK3O5wwiERii5BXCLJDoFlJkECfSXIIa5aQWq3InAUYtvmdbj8krN5y4Y1qJSLaDZD7Nn7BV559XXq6+3H5ZddxGtWDSOfDzA5PY+XXnuHXn3rA8zNtRAUysjlPUVI9lNaoh2rE1cEMyrFAKtXjmDdmhXYvHEtr145iLUrl6Gvpxd+TsDz1UnX7VClSG41Q5X5NI4BUiEPvj72vJjPI18IkAtyCIIcQEDYDlGr13FyfBxHj41jz+eH6MCh4zhy7AROTc4ijiRy+QLyhaJKLiil1nDKvGq32whbTQwPVHH1pWfjnm9ey6fv3grP9/HVV6O47+Gn8eCTL9DUQhuFQgm+74FlpEQJZVaGiYEOszBBVu44KIQV63HVQgmevpceVyE8RHGMer2GoUqAu268gu+69SpsWLcSzBL7Dh7FA39+AY+/8BZNzDcQ5ArI+wGEMAHKShtHEaPVbCrTPgCG+qpYv3I5Nq9dgc2bVvHyZYNYPtiHSqmAIPAg2FdCLW4hjGKEkUQYxZBStVvGMQhqY73wNUrWixPqlByJhVobY1NzGJ+ex/HRCTo+OoXR6VnMNUJEMSHwfeTygUVdsJYHWSvEzDYhNBKMY4RhCOIWlg9UsGPDCmxZu4x7SyU0JePw+Aw+/vIEnTg1D/Jy8HxhBaPQcw6pedHpSkk507tk3+iGrhYzId0wB+MnzpZrUK6LxKBamTIR3ewUVogap7sRWF3RTlfzACkpLAXgMQGxBHsEFqRyPKU8cjqgbRHCuOk14jhOBdZJx5tjpblwtoCwBpDk6S0vjGa9hpHBflx9xcXYsWMD91YLkGGIz/cdxl9eepPG52r45vVX48IztrHvE0Iw3v3oM3ryyddwamweQUnlbmeW0OJQZZ6IVYwPMdDXW8WWDWuwY/t67Ni6jteuWo7+njIkx5iv1zF6ahLHT05gbHKOTpwax8T0LGrNFuqNEPWWOhZKxrHFMmo1ihH4AkHORynnqyPUlw9h5fJBXjYygPWrVmLVyhWoVMsg4eHU2CT2HTyCjz/9gj789EscPDyKRjtGsVhGrpADoMweeAR4HuI2obUwh54icPvNV+Lbd9zAO7asg4wZH+/5Er/541P0zCtvoxYLlEplCMSIYmWqJqzAVgg5I5hCVkSJiaLMSPWMWhH1bGS4Mu0ZLHzUFxZQEDFuuOJC/ODO6/j0HRuQy3nY++UxPPCnZ/Hw0y/ReE2iWO5F2SOAZSoIstlqo9FuoVL0sHnNMpy+bSPv2roZm9Ysx/BgFYIizC3UMTo+hWOjYxgbn8Xo2DSdGp/EXK2JRjtS4SZSHW9PhNT+w8Dz4fuEIBAo5QP0lAvo7+1Bf1+ZB/p60NdTQW+ljEIhD5aE+do8RidncejYBB0+NYtT03NoNdUxZGoyJn5LTbTkZBokqCUGIwxjkAyxrDeH3ZtXYuvaYS4VAzRCiX3HpvHR3mM0W4vgFQIQCYhYCwexOMpC5velBFMWpKSsJkoLRReldT+HlJCN4ermk86m3FFxWGZANB9almTW/qbM3idON5Rdz75ZIdTpINJaGSmJmb1sw6XaZKqCAPWmZauTpJ4CJtiTbMEGYckoQtxu4ILzzsYll5zNfb0F+AI4cXwcr776Ab27Zx+2bF6Le799C68Y7oeUMaZn5/DAn56nD/YeQS5XQOAJSKnOlVMBr0LF+bTqKBcFtm9ai9N3bcfpp23mlcuG4Oc8TE5N4eCBQ9i7/zD2HThCY1OzmK9HaEcEQAUkKgcy1F9m9b/JICEEyBPqmDDhAc7R6XHcBoHhez6KxQDDAz3YvH4FTtu8ls85cxe2bFyNQrGMmYUmPtt/CC+98R69/tanOD42haBYRpD3lTKRSjiQDhVp1GoY6S/hO7dfzbffdCXWrhxBqxni7Q/24rcPP00vvvUh2jHQ0zMI1vQgmF3+zjYjbbYL8hbxl0hrYprwAGZWfRY+FhYWgLCJK87bjR/ceQNfev5ulIo5HBkdx8NPvozfPfIcnZpuIF8qwPeVL4xYHYUmQWi0WuCwiQ2rluHS83bxhWfvwLaNq9BXKaBeb+DQ4eP4aM8+fLrvMH11fAITMwuYq7cQxwrnCE+FqHieDwJByhixjMGsEBQYOhe9gPACeEIvsOij0Tyz2ukRcjkfuUIepXweveUceso5dRI1BZhfaGB8ehILrRBSKgVrJrVynZgTjjStjF+KpQawBIQMjmIMDxZw3rYVvHFFH+D5mKkzPvriCO09fBLSKyAQni7TSyx7Z64tJrC+ToAt9TkrrNzv7iWEyXjSWUeqPuvI17KjOLwlqYxhA/hM+J7dOe8UzDKBsZ01JNLchj5QAveYzJ6rJRoJhj1Agjy9GUDoFkkQmfUcEyZAAJQTt7Ywi4G+Kq67+lJs27qWPU+iXm/ijTfeo7fe+RT1RoSzzz4d3/3WjVwMYuTzRbzzwWd4+KmXaWqugXyxqhiTY0ghwIIQRxHCRhND/RVccM4unHfmDl61vB++R5iencKBgwfx5ZfHcOToGIUhUOnrwfLlI1g2MoLBoX4e6O9DtVxUBx54ns2G2mw0MTdfw9TsAk6OTdCxE6MYn5jB1Mw85hbqiCTg+3kUCgUEvloFimOJdhQhDCNEYQiWIXp7iti6fhXOP2sXX335+di2eS0EEQ6dOIUXX/8Ejz79Gu0/dBKFYhFBztNBkErgC99HGIVo1mawZlkPvvPNG/jm6y7BsqFB1BbaePODz/Hv9z1E7336FYJ8HsWKQo/K76nGQJ22ogNAM6mCupn5TKzz4As0m0006zXs2LgcP7nndr728vPQ25vH+NQ0Hv/Lm/jtQ0/QgZPTKPUMIcjllInGavXNEwFazSZk3MbOretx81Xn8CVnbsbKZQNohzH2HTyBN9//DO998gXtPzqK6fkWYuQQBD5yeuHCCKg4itButxCFITzE6K2U0N9TweBABctHBjA80M991RL6equolovIFwq6b+rEo1YYol5vYXaugemZBYxNTtPxiUlMzixgfGoOC402mIFiIYdSqYjA9wEWiQLXyl5ohZY9lcfSUQMCZgZHDKIYG1f148LTVnNf2UOLfRwancdbnxyk2VaMYqGYit8yZX2dnyqLrL4OZADpfaPZd7MhFAn6XhrAuHGggBFY6hflajCreAD0jscU6iIHrmYbzfpZs+nZjdWyz9Bfh7CARGAlFrkWVCTTjj2pJkur1cTWjatx/XVXcG81QN4TOHL8FB7+8zM0Nj4PKWOcfeZpuOPWG9njEMViHk899yo99+r7ELkqckFOmSuaKYTw0Gg0MdRbxJUXnYnLLj6Hhwd7EUdtzMxMY3p2DidPTaLdamNwaBCrVy9HX18vSoU8hOchDEO02m3tp5J6CduzfqpCwUepWEKhWIAn1PONRojR8Ul8deQkDhw6Snv3H8ThY+OYnq5BSoFCqYB8Ia8QGnwwMaI4RNQOEYYtLBso4/Lzd+PW667g3adtRKFQwPGxGTz1wlt44E/P0eGT4ygWCwh8H7GMFSISAkyEsNVEu7GA7ZtX4yffu4OvvPhMVEtFTM3W8Pgzr+O+h5+ir46Oo1CpoJALEMURknCNxLTJjm1KuzJDCKAVhmjWalg1UMHdt17L37nzaqxaPoT5WgMvvvoh/v3+P9H7ew8hX6ogKBQAHbvFwkcgArSbDbTbNezYuBr33HYtX3reTgz2ljBXq+HDTw/i6RfepHc+PYCJuSa8XAH5QCEohlqZFkRohS00ai0IlujpCbBu1SC2rluNLRvW8qa1KzHUX0WxmIfne4hlhLCt9nk2W5H2b0nHRwPkcgGKuQA5T8W3NcIWao0QpybncPTEGA4dP0VHT01jcqqGWjMGhIdcPo8gF8CzKFXPn0VSKFsBICU88tUqamsBPbkY5+/ezJvXDMCDxEJL4NX3D9KxiQX4+dzXCoZuf7P33TK6BZZ6XtYd0Pk53Y6vMUmZkz3H5r3i8FZndS0RTkTpMHr36tZYc0kpraRNCSzlpYRxsnUIMlMmszr4UWcBgPWJGIGlpKptn14qDht1XHzRObji8nPZlxECL8Drb39Af3nhdbQj5eTbtmUd7rnrFibZgucFeOzJ5+iNtz5CvncZPHNgInkg8iAjwJMhLjp/N2689hJePtKLOIrhex7ajRpq9Roqff0ol4sQBEzPLODYsVEcOXoCh4+P0vjEDOZqDSw02mi11AnMbtYK3/fh55QfpL+njGWD/Vi1fJhXrxrGpg3rsHr1clRKBbQjieMnJ7F33yF88MkB+uTzr3D81CR8P4disQSQBCMC2FMrWlGERn0BlUIOl567HbfdeDmfvnMzyqUKDhwdw4N/fpaefOZlzNUjFCplCOFDSujASRXUWas1gbiF88/chHu/fTNfdO5u5PIFHB+dxIN/ehZ/fPxFmpipo9xTReB7iKWKlSLyADbpjQ0fSUid20kQEEcRagsL6C0EuP36K/D9u27kHdvWIYpjvPr2h/jl/X+il974BCJXQbGnqt6VEh5JkPDQDiXCWg0rBou445ar+KarL8VIfxm1xgLe+uBzPPbsO/TuniNoxRL5YhGe75tzeuDpOKp6u4UwamP1QC9O27wG5+7exFs3rcTq5UMq9mmhieMnx3FERcbTsVOTmJyZx0ytgUY7RCx9xDJB+UIQhMfIeQLVQg6VQg69lSJWLhvAiuXDvGJkEAO9FQS+j1ozxOjYBI6MTuHwiSk6OjqF6bk6mHzkcnn4Qq+XarNQzWtWaMyGfpj5YnYnMNpxDMRtnL5xBBfsXMseIoRUwtufHqYvDp2CX6qoVXlCkg+sQ4Ag9VsqYDRj5nWbu93KWSz3l2m/K2cMRd300x3lF0e2JTFY6m6qMd2ubgLLdX67Aiv1jg5nWKpsAFpgaaLA7GujxBSkdBujVh03XH05Lj7vDJbcQhCU8OenXqSX3vwI5XIv4lYdK4d7ce/372ThhcjnSnjo0Sfo3Y++QKnSr1xIkGBSpy7XF+YwPNCDu+64ls85Yyfidh1RrEIISsUcivkc4phx4uQYPv38K3y27ys6dmIc4zMLaLTUthohABIByDPOZUMIMzqJQA8j5StBHIF8Rm+5gOVDvdi5fQsuOHcX79i6HmtWrQKRwLGTp/DWh3vwl+fepo8/O4YmJPIlHznhKee93kwbyRi1eh1FP8bl5+/CXTdfw2edtRNSCHz2+WE89PgL9Nxr76MZAeVKFQTWPhsJIZTiqc/Po+hJXH3ZhfjB3TfyGTuU+2DfoWO4/+Gn6LFn3sVcrYFq36D2f2r/ZWoyqFSFETzU52cQcBs3XnEefvq9O/is3VvgBwJ79h3Ab37/JD3y5POotQnlSp/aCkT66AMhwExo1OYwUPRx0zWX4LbrL+V1qwYRS4l3PvgCf3z8FXr9g72IghzKpQp8vYEcrPe+Sol6K4LgCLs3LcOVF+7iC87ajbWrlsP3BMYmJvHJF4fwwZ6DtHffVzgxPof5RoRQMsgDPH04rTpk1XdynWnXhBasACOOI72BWcAnid5ygJGhPmxZvxKb1ozwhtXLUSrk0Q4jTM21cOT4BPYePEZfHhnHfCOCn/ORywXKL6sTYDIIyQlMRgF4OgxATXLJhGZtHltX9+DSc7Zx3muDvBI+3j9KH35xBFSoqiDSruO0OKoy35dCV4uhs+yqoZUFKYSlwQglQdXkzJlUO12BZa6lEBSADuTloiVXGnbYr04a1o6E+255CTp2Vp308jigUIXWElG7gWuvugSXnX86R+06gkIVv/vj4/TJF4eRL/UijiOUfMbf3fttHuorQQQCr7z5ET382DMo9g6rlTmO9Uqgh2ajjtO2rMG377yJlw9W0W40QcTI5X3ki3lMz9Tw0Sdf4P1PvqTDx6cwu9AGCQ+5fADf99QBodZWdfbsdaOtUP8QWOf7UjFKcRSrMxTjCL7vYdlgDy44axuuufw8PmP3NvT3VDExM4c33/8Ujz75Cr313udgIVAsFhRKkpruQiCSAu1WHZUCcOVFZ+F737qBt29di3Y7xjsf7Mf9jzxLb73/EUAeCqWyjo3Th1UID1LGWJibRX+lgDtu+ga+c/t1vHXjasRRhE8/P4x/vf9P9MxrH6Ad+6iUSyAnoJSIIDyBWqOJVqOGC3dvwX/78bf58ovPRrEY4NDRk7jvoSdx30NP09j0Anr6+kGeD46Vj4z1wSX1uWkUAg9XX34BvnvHtbx14woQEfbuP4Y/PPYiPfvqO2iFAqVSRYcD6LxWgiDIQ61WB8ctXHDGNtx01fl87hlbMdBXwex8DXv2foVX39lD7312CKOT82jHDD/wkcvn9Kna6tw/M6rEUL5NLawMyhGkw3X0cr1BDmZbVTuKISFRDATWDPXh9M0receWVRjsL0OQQBgyxmfr+OzLI/TRlycwPjUPITzkcgXl/yWXd4z/Nh1eZO63m3Us6wtw3SW7uChaELkqPvpynD74/CiCfDVZRHOubFndrqzwWWynSVa4dZxrYH9Lt9sILPWoQ1+37OLwFverjQUxcsQcpGjDGwy9nAm4WKPd+/pH6/sSngqUk0i8YQbq2sGwG20FVJS04zcD0GjM4xtXXoTLLjqb0W6gUCzhdw89SXu+OIZcuQ8QEcJGDXfdfB0uOXc7R2GIr46dwj//5mGK4SHwc5Ax9EoKozY/jfPP2YV7vn0r+xQhajXgeR4KxRJOjY3jtTc/wDuf7KeZuTY8v4hC3gd5yZYbE8LPQqd00XCdSIBkeoDZdFgRyQ6QG6wpPA+QCoE1wxYKvsTurevwzRuu4ksvOgvLR3pxanIOr771CR549Dna88VBxMJHqVS1SxQgZbLEUqLdbGC4r4hbrjmfb/zGxVi/Zh1m5ht49a0Pcd+DT9JnXx5GUCqjXC6rFUVmdWSW74EjoFarY/lgFT/+9g18x42XYWSwD81Q4umX3sbP73+c9h8ehafHMJfLo95so1Gbx2mbVuI//eCbfMdNV2NkaBCjE+P405Mv4l9/8yh9fugkStVe5IIAUoZ6kUZtA6rX5hE3F3DpOTvw4+/dxmft2oqc5+HY6DgefvIlPPL0azRdi1EslaEW2VQYTaz73qwvwJMRdm7ZiDtuvpwvPGs7+it5zCw08NaHn+Oxv7xGe788gRb7EDmVBkg5wBWPCya7I0NNPjVcnnnG5XvnN3B6by1Iry5ql3AzjCFkhP6ih91bV2L39nW8fLAfUdwCE2GhHmHfV6fw7p6DdGq6Bj8oIhfkoNwhEmBfLUIJ7T+zW4yk2psrfKDdwGDJx/WX7+K8aMHL9eLdvUfpg/2jyBfKitvYNdkWBx3m96xDvlvgKYBFF166mZPuM9ZvDgsC1Yo0s10tpeLwZsdcUVsmXIlEejlX6oEDkd4wmxZIRJTyX8FMGGc1sVvn1BwnKzSAhDHcAzOTvBEqxK7dbGD3aetxx63Xcas+j3KlDw8+/AR9svcr5Cu9IPLQbjewbeNq/PT732JEC/D8Av7f//xrOjo2Dy/IWQHpeQKN2hwuOfd03P2tm7jVrCGOI/SUi1hoNvDsK2/Ry699jFotRq5cgef78IgQsErMxsLTBNXxJs7KqtEYQmYRJdnNz+Y30SXlsFCrGJCkVveajRpk2MDubRtxz7du4Esu3I2hwSqm55p45Y1P8Js/PEl7Dx+Hn8+jXCiDpQp+NO7AdruN5vQc1izvxffuupavu/oSDA0MYXx6Hk888zr+8Ofn6OT4DIqlCvxcYLNkkGCAfDSaTYSNeezYsg4/vPsmvuGqi9DX24t/+tUf8f/8H7+kXKkH7TBCY2EWy4Z68IO7buYffPtmbFy3Agu1Jv7y4pv4p1/9kd775Avkyr3IFys2skMJBom41URrbgZbN67Ej797O3/j0nNQLvoYm5rG0y++jd8/9BwdPDaJYm8PAl+ZTiZGDoLQbNUR1Rs4bf1q3HnblXzJBTvRX62g1mji9fc+xh/+9BJ9uv8E2A9QLlV0uqQIdnM1s0bemjedNC5E6gSY7ApbN4skiy6ERtIQPgBCGLbRbrZRyjPO3LES5+/ewtWcj6hZQ1AooB4RPvtylD7acxiTC221Mmm2vgkCa3+hEVjK06DrIkKrUcea4RKuv3Qnx80Z+IU+PPf2XjoyoQJulcDqnlVjKRT1df6sbKyW+67J3qq80WzRVJZWtkxO01ivEiYPmclinWF68KQhkn4oFRCqLyOwbFmWsInNrGVTWqhZwmh0BVNPsppANtMhodmsY2SoD/d+9zYu+YxCoYi/vPgmvfDqe8iXqgCpQwuiZg0//P6d2L19HQcU4/V3PsX9jz5LxcogojgCwBAeodVs4Mzd2/DT732LuT2Pdhii3NuLfQcO4Hd/eJqOnJxBoVSA5+vsmDqlhk++TbOrcm65AstkhNADaDZIJgTWSMIIKRfuuxdpTcNac3uIINFqNsFhG2efvgn33nMbX3rebvRUizg1OYtH//Im7nvwGTp6YhylahF+4KlsNfrwDQkgbLUQNRo4fedGfP87N/EVF56DcrmMw8cn8NDjL+JPTz1HEzM1VHv7AQCxjJJYPSHQaLYgWyGuvPRsCAG8+s7H8At9qM3NoBhI3HH9pfjPf/Nt3rFtHdpRiNfe+gj/+puH6C8vvQORK6NcrUCSBLFQR0B5Au2I0Zyfw/rlPfjuHdfzbTdcieUjFczX6nj+1Y/wH/c/Se99vA+5UkE51MmHnalCoN1sod1sYt2KIdx1y2V849XnYbC3jEYrxqefH8QfHnmRXnlnL6QfoFAuQpCnIsrYbPxPzuUhIrvMQyJ9wrUwXLoEYkgPYXrCCm0tEARYMGIGwkYDI1UfV1+0izetXYHawjQ8TyLIlVFrCXzwxWH66LMDiFBEkC9Az3uFtMgNDLWBAJAQiFp17Fw7gIt3r+I4bqPGFTz9xh6qt6EWJIwmYw0FFrGU/lp0lX5Gt9Ex9cwimWTWAa1JlL+RD6oMcwZBplxrEnJ3wmehXbah3aCfaYAKDNSN/5o0vbp2vVIpOuoSiCDhgwA0a9P4zl23YcvmtRwIwmd79+N3Dz9B+VI/JNQp02FDYs3yHvz0x/dwQG0IIvzzvz1Ix6YX4Ad55cT3PDTr81i3ejn++8/uZS9ugmULld4BvPzme/S7R55GFAcI8mXlm2Gp2gZYJpQ6PYs6TsmsRwEQUvvFAAE/pQiy9JKOwHL9iV21HqB8EMIH4KFZnwOiOq64+Gz8zXe/yWft3gLP93Hw6BgeePRZeuTx5zEz30SxWkHgCXOsDHQKAjSaLfgU4RsX7sb3vnUjn7lrK5gZ+w6ewK//8AQ9/dJbaEigUq0q5WWUiFDar9ZsqFAVKeFxhKsvOQv/5Sd388XnnY58Lo/393yBf/vNH+mPf34ecy2Jam8vPFapVySpnFOCCfO1GnqKHu648Qr+m+/cio1rlgGS8f4n+/HL3z9GT738LmLyUS4U9JQU2txVcVC12XkMVH1886Yr+Fs3fQNrVgwijmN8/uVRPPCnZ+m5l99FgwMUqwPKpOPIzCCl6YVB9hknccY8EkKoU2e6TOTU+JpFKMsPanJ6Ll8TQSAGkUBMHuJ2A2jXcMV523DeGadxqz6njponQj5fwMnpBl56dy+NTrdQLFYhEEFjcBC5ezdhLSHhAbK+gMvO3Mgb11TBEDh4qok3PjhAXrEKRgQhvZS7phti7CaYF+27XuF3UZcURq+I5LRqvXNC8TUZIbBk2VQa2Zr4jRwzbzGN8XX3ssugJpWMdKSrWjGkTjBhC+qyC5wZIA/txgK2bliBe759K7dbTYSS8Itf/54m55sI/CIIEuQRmvN1XHPV+bj+qotZxk0cPHwc//7bx8kr9yitKlVbAq+N//J3P+A1ywfQrC2gp28QT7zwOj301AvIFXrgw4OM2WoLkdFCNlTBIiaThzvZHKyyHCT96Rab5gos9xn3SiZRkgpIEAFxjFq9hmIAfPP6K3DPnTfy1k2r0QxD7Nt/Ar976Gl65pW3MN8M0ds7oBAgK7gkKFCBj/UZlIIYN159Ge7+5rW8ecNqSEl46/3P8a+/epDe33sIhXIvPD8AEEFQDBIeGvUmWrU5nLNzC/7uR3fzLdddjL6eEg4fO4X7HnwC//77J+j4xDz6BvohSCAOQwBSb5L2sDA7DQ8hrr30AvztvXfwmbs3wBceDhwaxX0PPY0/P/UGTdcZhWoBRBIcA6TT1cg4xsL8PMoFD9+4+Ex8947refvWNRAEHD0xiYcefxkPP/UyzTUilMs9IM8DI8kj5enDNyXBCizWIR4mQ0BXhMH4eoHlsjNUPBGB7Nl+BjkbgWhGW4IRNRdwyZlbcNnZm7ldn1M7NjlWyf7iHF7/5BB98uVx5ItlvQGZOgRWyskdxaj4bVx/xQ7OyTaQ78HLbx+gk9MteEVfKzFhFywWM/+yfJi9R2S24aTrBxFibXGY3aMqfZCw4KaDx7vxPaDisOxs5PRDX3d1Q1vZxGDWiawwq1MB7HKjMj3dn4U1E035MbNKNRG38IO7b8OK5b3s+z6eefEtevn195Av96hwFRnD8z206wu49/u3Y8v6lZwvlPHHPz9Dr735Mcp9/QBJkCSEjQZuu/FyXHPVedxYmEeppx+vvfsJ/cd9j6JYHVKpY5g1XO6OPl1tafpns0/aPppo/HQZnClrcZobqGzwMjQyUGlThE5SKKMItblpDA9UcNcdN/G3br4KG9YuQ6sd4f1PDuGXv/0zvfzOe6BcAaVSBRyHQKwCMiUEWMaozc1i5Ug/7rj5Sr7j5iuxYe0KSOnh/odewP/9H39JKPdCeISwUUd9bh5b1ozgb75zM3/7m9dh9cohjI6P4w+P/AX/8bvH6PPPDqHUN4R8qaCyyAI2g0K7GaFdb+DMnevxtz/6Fl950ZmoBB5OnprEI0+/jv944Ak6PjqNnn61cih1uAUTwRc5NObnIWQLF5y1E9+96zo+74wNKObzGB2r40/PvYYHHn2Sjo1Oo9Q7BC8I1CG6lifVQo4weyOJLB9KZ7IROUhKp4IhEIh1RDo6J1g3/46+od5nTpXFet4JZ/eGJB/t+QlcfeFOnHf6Bm7WZiAoQBw24PsBRKEPH+07Rq9/+CX8QhlMvk6ox+k5BgAcwwOh1ahh6/ohXLxzDTebC5ho+Hjlva8IQREQseMvzggISk69Mi30jMDKoKJ0OJOirQnLUDnQ9HMavMARem69aXom4Q3MDF8vVyW25CLaves0+iuEmqEhMSFxRSNBc/Y77OpMcmqGWxej3ajjtK3rsWrVcg7bNTSjFvbs/QJeoB2ICp4gimLkCzkMDQ0yBKHWDHH0xDhEEAAyBvkewqiFZcN9OO+cM7lRq6FYLOHAoeN46JEnkcuV4AMgqeV/ely604AZrjyxM8DcS361/f668BG3NJvlwElfTOyUJhmeEOjtH0ItjPBPv3yEnnn+Nfzwnm/yLddeisvOPw2n71jDT7/wNn5x3xO0d99h5Eo+CoUCJCsfIQmBvsEhTLck/udvHqPnXn0P9959O69dsQyvvf0ukR+AI4mZsXGsGK7iv/393Xzv3bdh49qVWKjX8PDjz+P/8y/301vv70GuPIC+FashZYxI6kwHfoB2W6I5N49N64bw0/9+D9956zUY7K1iZnYWjz7zBn5+35/p470Hkc+X0DvQr4RpHCnnMASatRoa7SmcsX0d7r37Vr7y4rNRLecwN9/A48++g18/8Dh9su8EiuUe9A0sR8QxOI60yW4mmvElOUvmRlBRBk3oewKAPWvM6OC/hv9To5gUaBCuKs4kVDE8EiNX6sHrH+7H0FAfNi6voN0OcWp6FuVyGUOFAi7YtZaLxRJefOsjQq6CJId+uk2SCYCEyBfx5fEpbFs/grIHDPblsGyoiBMTbfg5tf/TXTXsWFRQH7TP2SFayv/tuDbI/NXdtrS2ji3VPvcIwC7WhyEa6ywvfufNpU2SbldWo2TjrxRI0UFvZtlSd9WZy866WrYCKNXHEc7YvR0eMfx8CZ9+tIcmp+dRrAwiZgk2BxhIRrFURLlchiBGs9lAvbagkvoTgVhpnDMuPw891RJqc02wl8PjTz5LjaZEkPchOYKAWoXpFmfWjcBuy7vRcDH6fR3jmzawWUntUj9YmR0ggpcL0FMcxNHJBv7P/7d/oUcefw4//N6tfOUl5+GOGy/HeWfv5Eefegm/e+AJGp2cQ7mvH56vAk8lGLnAQ7FvGIdPLuD/8v/4d8oFHtpRCBnGKPl1fP/Wy/B3P/02n7V7OzwR4NW3P8b//MUf6KkX3kSMAP0jq8CAigY3h2TGEnPjoxgcqOCnP76Ff3jPN7Fh7QjakcQLr7+Pn//2EXr5jY/BXgV9AysQy5bazM6AJ4AwbKE+P48NKwbx/bu/yTdfczGGhwbQasd44bWP8OsHHqdX39sDUaygMjigDjNxVqy6mmoOnxrLQECnNTHjquenkA7PLlHWYmNr+EMiSSTAlE6ukyi/CEweYpHHq299RGtuuYw9IbFsxRq8+sa7dM6Zu3ikz8fpG4bAcie/+M5nhFwJMYvUcWCGd5Sg9dEK2zh0bJLO2LScIxlizbJeHhs/TuByVwHsmn0pQajRlZXdXemBLjKEu86hVN+durutxPr2hFWNaszhn1lTL6V1dGCizQyqHbBqMpkjirJluPEeyaqGMbmSwmFmaKpeGcXoqZaxfGSQw7CJIFfEwa+OwPN8rfi0GakCgVCqFFHIBSBuK0aJlSCDlIhkjHwuwNZNm7hZq6FYKGLP3i/x5ZcnUChVEXMIwLMK1WoYPVjulTWBDb2yQlut3iQ71K2JyNrRTqRzmGcZPwlzyI5JpiEwZigB4ChCwc8h3zeIj/cfxf/uf/t/0TWXXYgfffcWPn33RvzXH9+JW6++ku97+Gl65KkXMDW9gHK1V42fZEQUIigFyIsCFubmQWEbV194Bv7+x3fzJReejiAnsPfzL/GL3/4J9z/yLM02YvQO9IMQgzkGmNTYgDA7NYVyQLj7tqvx03vv4F3b14OI8NGeL/Fv9z1Kf/rLK2hEHnqqvSAw4qilJrPvIY4Yc1NTGOkr4Affu5m/+63rsWrFICQzPvr0S/z2oWfoyedfB5OPnoFhlRxQh93ovJ+anRz0IdQBqD4RYp0znrQgyU4xY4rb1Wwg8WE5bgw4Y58ob7NSph36BuHpVXbS6N2GcZJZThCAYBDlMTEzg4/3HaJzT1vDggnr1m/ih554he65/QauBjXs3LAMszOzePuL4/CLPYDU+zuhhQ0BghkeqyPgToxNYcvaQQReiP5yHoWch3mO4cNL9QkZRW366Tl+aCOsupnAWYWd5OaC9udBbxVaPEQkKTtpg0/QS4yLmD1/rXmoakjs8GxpWXvXlN1FJzllJD+FYQurV21Ef18/4nYTMzPzOHJ8FCIowAyOOoXGA3mA7wXwRQDmSB04QLDCuN1qYcOa5RhZNoBms4lcoQ9vvPUhtWKCb0O+dAriv7rvS6OnxehoItPNgZnWn7jE1c13aM0BK9wARhtgQrlYhsyV8fSLb+PN9z6g2264Et+/+2besXk9/rf/5V6+9fpLcN9DT9HTL72NSKpgWC8I0KrXEdbncc6ubfhP37+Vb7j6MvT3VnDo+En8+veP4Nf3P0HHj42iOLQM1Z4SEEfagR2AhIdWvQZuN3DNxWfi73/yHb743B3IB8Ch4yfwuwf/gt/+4Wk6MTWH6mAvSoUAEUcgIrVbQPiYm5lHJcf47i2X4If33MqnbV0DEGPfV6fwu4eexqOPP09TtRaqAwMqT5nO/+6xsMJAEcioSHMMqDbEOHFROBZ9etzsv67SSrsyeNExW4x/KGUAGuSR1OaDSIIk4HlVvL/nEDatX4ESSawaHkEu14dHn3qDvnXT+ZyP53H+7o08PrVARyYboFwuwytGGDLI9zFbq2N6toaRgQCFvIfeagnz0w1Q4KenXWYKOl1Pdz5DL/O5K4+qm7qMzC6YlEXmCsp0Q3w2dqbD6O5LboW2jVlNbypjtcJiJaj2VltblhKhtZQgNONvOy4ILCMMDw+qTAeiiMPHxmih0YbIFQHSWau1FhWCsVCrK19WECAXEILAh5RNAAwZRVg+MgjPk6BCgGMnxvD5l0fg5/I6waCnYfTSAqsj5MPx0nU3qw2LklYQiU+AoDHYosKqUwm4dbttsuYHKROBJQMe0DM8iBgSv370Ofzl5bfo9puu5jtuuAxbNqzGGbu38fOvvklhK0QUxpgbG8fGdcvxs//6Pf7WLVdheKgPCwtN/PbBJ/E/fvkgfbT3KxQqVfSsWafyhknlfPSFp05Anp/EGadtxN//5B/4lusuQ281h4mpOfzh4VfwL795mPbuP4xitRd9g8M6p5Q+zdoTmJ+dA8kIl5+/G3//k2/zxefsROD7ODY6gYeeeh73//EvdODYBHr6BtA31Ic4ihUPmGU+cpCsK2wsr7O9RToYmhSk6KCjJrAzCsbXmxZU5olkLJTyNpPOLMzYGgxaS2pUpZNynwjWW5x8DzO1CEdOzGDnmn7kEGLl6iF88OlBvPzuQbrhkh3cqk3honO28+iz71GkfZmmXckxG2plNqYAc/NNWjaYZw8RqqUcaKIGBFppmmPOROfCV1a4uD7ADjSWEWAKbXYDKJ3XUi4S36LRTMXZSxhoqwuUzsR0jHsVGc2ue90MrHYCZJqczRmvX7BQOmEaRrlUggDDCzzUmnXIWB2ZZASFYSLheZhbmMfE1ATWLBtBtehjcKAHo6MzlqkrpSooJuQDH6fGTlGt2UCxVFVCl31l3jrtt+3LENOEbgiov+YcnOylfBdszT8VRa0mmgmA0Kzt6vIUvSgzObJXIqz03jc2gkvTN1bmT09vP2YbTfzTv/+Bnnj2FQwNDOGDj79AqVJBfXYSQ/1l/PhHt/H37r4FG9etRBRFePy51/Gv//EAvfzWHgTFKvpHRhDFerM0PAhfIIpizE6MY/WKIfzwxz/hH9xzE1YM96Nea+HPT76Cf/7VH+n1D76Anyujf2QFIhkhBoN8FTzaaDTRmJvG6dvX4iff/xbf+I2L0ddfxtRcDU888zr+4w9P0J4DR1GpVDE4PAzJytTy9FJ6ItRJ75dTn0lDIkKCm5XJaMVMkiI8M+EUf6oEfZbXs+PRxZxJQTYyccOdc8vlKVZLlDrVjE7FLRiAj4lTUyTXDDK4hXLRR1Ao4sChUXy+cgAbhnLoKTC2blqGT784haBQBVOkFmWIwOSBmOAzIxaEhVYbauq3UcgRdLCObZ/NEuEgniVdRF9jESx2mXliAnPZkS/d6AtAOd3da1E/CSXf2Xaqs6GLmUCqk5n4KuM/43Sq42w8GAGAIJtvx25wdaQ6gdWR5STAEAhj4MTYJK1ctpwJEuvXLOc9H+0npioARj7vw/eEMj1mFxJ0mBGqWZjazWG4lNro6si0heulYmYdwqVjgZDQgFIoz9A/K9SyvpP07+m6lS8vyOWRH1mByVqEU3MnIXJ5yNY87rn9Wvz4e7fy7p1bIJnx4af78B/3PUwPP/YyWkzoHRoGQIjabeVnEXmACfNT0+ivePibH93OP/nBndi8fiXiOMSb7+3BP//7A/T0828j8goo9QxA+akiu7wdhzFmZmexbkUf/ubvfsy333gllg31o92O8NTzb+Lf7nuU3nhvL/LlXgwMjKgN5RIgJPyYHRuXt2DQrEsjh6zs+BezC0d2fK1gSaME1zGdmsTCVcDJfLFjoNGGzXuVEnbJuBkU02xHKm5JAqV8jklKkl4e7+45RCuu2MmiVcP2dSN85Og4NaRKxSN0/CBsRLlqbxRpNEvqBCa17SptPS3mGM9+/muF15JCLSVnkkUQQ3q3Hp/tAFBqoriowixMWSTkjF/Kf6L0OczAd1slgFN+tq1u56yjUiMSk47FvqRvsv2cFR6Ezz8/gDN37UTcbmDjurUICuowBhI65YuOG2k2mzqY0gSyxegiy//qy5rJ6V7BwGLTxliyTXZoZlB6YJPfAZd6mboy31MM5NbODEEmP75KzyvbLYiwgWsuPAM/+9G3+fyzdyDnCxw4fAK/vP9RPPDwMzQ13UDv4AAKHoGjEGCCRx4QM+oL8yDZws1Xn4//9nff4/PP2gYBiQNHjuHffv0Yfv3gUzSzUEPPYL9Cw7HaGK727AFzU5PorRTwd9+9kX/0vduxZeNKhFGE9z/dj5/f9wg9+eyriKgAypUVAWJFv4iTQESC6DjcpKulYMwyMzk1IyfCP6Fwgmadu5y4OLpd3Wi/ZOjKYuU4R1iZmL6YWSFKKbVzPIYX+DgxMYVDo7PYvLyKnkBg7apBfH5oFsLPp5jFKEoG6XRHyu0hhNBnIHTvQ7c+mvK6KfHOLprxMHIhoQ6rG4lMcZ/X9LMnjuvL1yMArQZSA62WedW9RFZwshk0aZb6VyfBYyZ0O0cw5ZuCmY5pBKA+sDUxVdsEIDVkZoaMJXyPWJAG7OxEsjABLJEP8vj88wM4eeokRgYqWLdmNbZv24TPDpyE5+cgWa/wQaJULWpCeiCKAIrB8NUeN4MAM4PWFckYptDy2yBRAGApADetB0FleoAZfEMDjRK7WeYOMFhMs6XMRhddqbcU0xOhVV9Aqz6P07dvwH/+8d/xLddcgkqlgNGxaTz8xEv4t98+TAePjaPS04/Blb2IImW+MQR8IdCs19GszeOCs3fi7396N1//jfPQUy1gdGwWDz3yIn7xuz/TF0dPoFTtRf9wGTJWmVwV8iDMzc7B5zZuuOpc/OxH3+YLzj4NggT2fXUM9z38JO5/5C80MR+hpzIIrs3jonPPQL1exzvvf4pSbz9yhRJgTrTJnGmYpYdVqE5IDQSpqHaD+klFzphI9BTCQBKOA0pbEd34ID2ehoddC0KX6aBttxSzD1XpNiXgg0BAkEQoJeKYSQVXKzBx9OQkbVo5yBzXMdLfw/sPThGx9kmZHSWUrIQW8j6EYHCszkNkJp3kyFLHtrWDBTMoPrsa3g3ldxNmNjGCnfMZmWJ5PYnnIlAaRhiydkdHTmWu09IOhkFZQJr8ye3EvE8PqssES0n3hYUFkCBEUYhCoahs/TjSO9gZBAmCp5zNvoeF+QbeePN9+s4dN3K7OY+bb/gGH/qX+6keStSbDUAQwjjCyLIR9kgQcQwIVn4VJH60pWjgMrXMCLb0QCZaLjFJMjFdOpuqTsmWIaEioks318TpvsLivM0qhW0YR1iYGsO6VQP4m5/9iO+4+RqsWj6IhXoNv3vkZfzLrx6iDz87jGKlB/3DyyBZoq3jqTyRR9RuY3b6FLZuWIkf33sv33XbtRgerGJmdgG/ffpF/Muv/kgffPwVcuV+9PQPQMYx4jgGEeD5ARr1Btq1eVx81nb87Md38lWXnoNi3seJ8Uk88PCz+NXvnqDDJ8ZRHRpCb7WAshfj//B/+u/87VuuwNj4OB54/CXc/9CTdOjUGCq9Q/A9AqKoy6RJ5LW7Qs3mO5RONeEKcH/PmChZbOsKtMUmp3nLLMvbtgnRHSqnyk7aK6Xy/Y4MDdpXao0mpBCQFIO8HGZmamiHEj7F6Cnn4QsglJGqhD0YpW54sFTIQ7A6Aq4dRYhB0FOo6zz8OnmQ7XvKOsvSByYINNm0DUBlgDHb+kTame/W7xMoPbDGzDIvgK1A6TA/wDqOwoHLqdA1few8MUjqFQu3U4DVeinCsNIFtq/EIC/A2Pg4GBJR2EZPpYgg8NCOAc/TyASeDgxlyJiRKxTx3gd7cM5Zp2Pdyj4sX9aPG66/FA88/BeMTc0pSMwxlq9Yjt5qEfVWDHi+qdI6XBcXoY4+IhU/I1XnkncME2Rgt30JLnMY2phVLQl7wIaV9kgmWJcxMb+xVOhYag1PiDEzPYm+ngL+84/u4O/feRM2rFmJdhji1bc/xs9/9SA9+fwbELkqeoaHwDKCDBsAEYQXQEofs1MTWNZfwt//1+/zvd+5FevWDKHZbOL5197BP/3iIXr25ffg5YuoDA4CUEexEwDh+YhCifmpU9iyYTV+9r/+mO+65RsYHqhgeraGPz/9Jv7nr/5I73/4GSo9gxhesVrtqYsZTZZ44a0PaGiwyueesRV/+4NbcMVFZ/DvH36GHnnqNUzXW6j09kIINW6CYA9SseOoSWZMkBTSMlTXgqljgjFrZ7AWUJrXWZujarUsuW9wNQmhvSNKkQtjleh50sE/bp0gqGPuPeWzKgZYuXKY47gJSQIT0/MIhHKkCy+HZjtCrR2hmhfI530EOUYrkgD5ynwHg3T2VgGJSjHHKveYQH0h1AevJnM/lcsrxa9d2toFbZFzz8Z3mvJI8/eSk8pVIgmRmBm+LsEZucy7pmKHuCnHcaJLkHIim/ctIrVW6hLtNM5IMhaqYjQp4fsBToyOY3JqDqUcoaenjKGhXhw5PgeR83VbjeNUmR9e4CNkiUcee4r+80+/x7IV4spLLuDRsWl654NPMTW7gKFqDiMDVZx31i785cX3UCr0I45i0NJNdejj+jX0ahNl4b+hW7KJml37zlLSCCVhZpFLnJSNn72ywktC2nxbtfkZ5KBSvvzkB3fwrm0b4AuBz/cfxs9//RA99sxrWGhJVAZXgUiqk2kkAazyoc9NzyDnM+65/Ur87Id38uk7NoA4wkeffIGf/+pP9NCTr6LWjtAzMKSaquPdPEGIY8bM5BiGByv42X+6i793183YumkNoljiudc/wD/+8iF6/tUPAK+EwRXrIWWEkFUqGyGBkIGHn3gJf3nuZbrhigvw3duv421b1uB//S/f5xuuOg+/eehZeva1DxEKH/lyFZKSoEwmg6eMUu5EoSkT2jziWgLGLWDHSH+2H7qOBhZjHrtnNoNg3PET5KnUOyQQN5vYvGEQIwNlRLUmFlrA+EwNvuerfY9CIJIRIpaQ2pHu+QJxS4KE2QMoEYMQRzH6c4TeSgGxbCGUeczVIwi9KTwR3P//u1jPB3dTXlpdu88uspCn/yVB8LubELC/ZVP8Eha3bV2YrJ5LTrexsHiJ+uzvjoa0QswXmJ2dx8mTk7Rl8yoGt7Fx/Roc+updoJQzvlhAHwOm2iGQL1ZxfGwWTz73Kn3njps5bMzj+3fcxFNTM/TOR5/SXbdczbX5aVxxyfn85tsfUztuIeYYRB6E2Z/1NXB4sdXU7P1EL4iu9x0i6BuGiWVaWDnCK6FjGhl75KFeayBuz+PS83fhp9+7nS8873TkcjkcOz6GB//0HH778BM0PlNHudqDnopKEKgi7wnkB6gv1BA3Z3HJ+bvxX376Xb7y0rOQzwFfHRvFfQ88hd/84c80Ol1DuXcEvWUCcwxJUmWTlYzZqRnkhMR3vnkl/v4nd/PpOzYBrFYef37/Q/TgEy+h1iT4Xg5FEWN2egK5fB65fB4xxypVkGAM9PcjiiI89PTreOnND+ibt3yD7/nmdThj13bs3LqZ7/p4H/7jD4/RK+9+BpGvoFQpW/NcKXXWYQuJQs3umTPKRRqeBdJna2ZoD83KbloatpIMYHcrj22L3vS8hEmpipaQ0JuOuYVzd23iHFrIlar47OgpzLdilEpFtUcSKl24Qm7qwF81Z7TYZJ39FgJhu4GRkX6UAoGICbP1NubqTZBXtCEVVmh2nNS8dGhDRx9s/9K/272DGUCwmPyBnTvaJARgncSGXKlPxqSD0RuJCdjhnHQ0hbZkFKM4zJLVPaksDUY4ZQ6ZUCf7CkQxsPeL/di2dR1a9QWcvus0fuOtD0ntCA8UcYSnaiKzlBujXO3B+x9+icGe1+iWay/idruBH//g2/znp56hI8dOYbivhJUjVVx1+fl45KkXkC/3wG6lkck2G5vQzTVr2UFLnGRFzY4U6RVIJkJsfCoZOiZXcqKyS2PXlCRFGPMQIi2kBXloNepoN2o4Z+cW/OC7N/GVl56Fvp4yJibn8egTj+NXv3+cDh8ZQ763Dz09vYrJI5WXSZ1M00Zjegq7t6/Dz/7mZ3zL9ZdjoK+Ck+MTeOTxZ/HzXz9M+w+cQLGnHz29g4g5QswCJAhC5FCbr4HCOq6+9Cz8w0+/w5dfeAaKhbxaefzdn/HbB56gU+NTKPUNY6Ds4fwzN+D7376Z9x88jl/85o90fOwUKr39IF+ooFIAvh+gf2gZmmGEXzzwLL3y5oe457Zr+YbLz8WFZ2/Fjq1/z8+++j5+/+cX6ZN9h5AvVZErlhTvMAMiUT6LOsqBlLloQK7lWysBHVNJalPKjpcz5hl/lovwhFsG0hNWYSUfrcYCzt+xARvXDKE2Pwnp9eDLr45RzleGkcoWGiPnCwTCB9DWJ0SbVMoCgj21WMJAgAirVg5yJJsgL4+xiQlqR5FOgNod8XUuXix+2flqTOSEwFbIuOEli72fKGakBBszq6PqE8DGHZHWVjvA7FhXE9RGs2cqdzW+2htl4imUU9p1qH3dZSAqS4mYABlL5AXw07+5i6tFddrLI0+8RG9/tA/Fci+6CQqQkegCYWMO1155MW665hKO4xj1ZoivDhzEti0bIXyAKcC//uJ+2vPZAfQMr0QsWftDjABUxCd9Si8jAYNujFk2aFZNBqEFSgKJ2XlmqSvLOK7IJwBMBOl5iFsttGuzWLd6GD+4+za+7bqLMTjQh/laC2+99yl+/quH6O13PoUoV1CqViBZJSUU5IHIRxRL1OemsWqkH3977x18z7eux5qVg5ibn8fTr76Hf/y3B+ntjw4gVywhX/D1ym2SeqTZaiOqzeP0HRvwX//2u3z7DVehr7eIk+NT+OOTr+Cff/0ofXHgOCqVPgR5RtRqoS/v4//6f/wHvvaS3WAw9uw7gt8++DQ9+vRrmG9L9PQPgjwPiCN1mo/w4JGHRm0e7XoNu7aswt23X8OXnH86hvurmJqcxlMvv4/f/+lZOnRyCoVqP3K5gkYfzqIHOSa4oaWxDoxyMONlDp01E04tJVrUpqyIJJwHMDsWkpOxJekMEdqMcy0VF/EREcjLoVmfw4blVdx1wyWclzWIXB4f7hvFM298Sn6hR1kRLNBqNjHSV8D1l+5mkguYmJd49tU9FAUBAB++Pok7bLWweqiEK87fwVFzCiEX8PK7+2kh9CCCvLaCkr6bVDFZZWpSGSW82GneMhmQ4dx30itZALDIxvTFjgYDoAWWmonWwZXVBuolYdMls7Hx0CmwzCTSEAAgYX0BFhar0bKD6V6p8hJZAckSUgRoLizgorO347brLuV2u46mLOIff/F7aktfaVFwpgzWNrRyXLfqDVxw5jbcdtPVHPiMen0OMas0y8SEMBL455//lo6NzaJYqULGCt2ldtVrgaV6qIXZYvDePqcYwBxgoAy9bs92Os84JYcTocdQDMQssTA/h/5KDt++7Wrceds1vG7NMrTCCO998AV+9fvH6NV3PkEoPVSrVUjEikElAZ5ioNr0LHpLHu649Wr8+Pt38s7ta9FuN/DOR/vxj//+ED37ynuIyEOlt1eRVEpIofwtHEeYnxzHmpVD+NkP7uC7v3UdhkcGUGtGeOaFt/DP//EHevPjfciVe1Ep5IG2REwRJBHiVghETVx1ybn46fdu5nN2bUSQL+HN9z7Hb37/GD3/xgdoUR7FchnEsTaTpNpCRQK1Wh2QbZy1axN+cOf1fNEZ21Atl3D81CQeeuJlPPz0qzRdi1Cq9IKENo5IxYCRORVC86EJX0iZbAyF0IjsohGDAU/oMyD0iqRxyqcmcWLK2430SIJHjcg0K2MEvZLbaGFZfx533noZV4IIFEeohQL3//klmmnn4XsBAmJAeGjUajjztLW4YPdajtsL+OLQNL3x0WGgWFDWAdS2NT9u4IoLdvNgRR2G8cnBU7T30DT8XEm1XZj8VIoc2fzqCe8nkWlLCSzbOy0IIRPBnKDX7uhtse/MDMoPb1FL1mpe6/w5aWHlvmiu7MkYHbYvAcq00d+NzZ9pDHfSJMkCYerUKyuSPIBjUNTAz354Nw/1FVHq6cFLb3xIjz71Gio9g5BxOyNA2PlfFdWo1bFl/QrcdtPlvGbVMNrtttrGQgQ/yKPZYvzy17+nz784iGLfkDI3WWpBk9EKlCa8e6VNuc6EbzLzbNJGU555P30wiErkr87dq9fmkfMY119xLr531428c+t6MAS+OHAU9z34GD32l1fQlj6KPT0qvY6mgQcBgoeF2jyIW7j6srPx9z+6i887cxuEJ3Dg4An8+68foYeefBmzLUa12muZmVltf4piidrMDPoqAb5/5w3803vvxMZ1y9FsNvDux1/gH//jYXrquTdAuSLgCcRRjJ5y1SoVADZ4d36hjoGePL557cX8vTuuw/ZNqzBfa+CVtz7Cv/3mT/T2R1/CK5ZQrJbAMraKzBMeJBMWGnUUhMQ3Lj4bd958BZ+5bT0C38fnXx7H/Y8+Q0+//A5aUqDU068O+5BSndGHzonnmnLZE5jTqMEMvzaBNOKSAoBHKqU2UWol3O7tMyiDWPOBB44kmgvz2L52CLdccyH3FhntdgO5cg8ef/59+vTAcXilPnjSgy/0cWONOm6++kxe0RcgDCVeeX8fHRxtAjkfQjIAH63GLM7ctgpnblvNMpzDQsPDM2/to9grwyeGtMIqLUA6BBFgt9i6h52yRZ/6XcPTRlATmUQUmbnvINIuqMrW66K1wshWMCERWEi0TtZ34i53EnU65JMK9GQTDNKnvZjjerID301gmY4azyHBdFgNfr1ex45tG3HvndczR3XkCxX8/LeP0L7DY8iXytZMIVOG9i1JkzpHeKgtLKCnUsD1V1+EC87ZyYFQp5gAQJArQLKHPz32PL32zgeIyUexWALZ5d/0ILoQeTH7PAlVSAZiMYGVxGCZAEItsDQqIPJQb9QBWccFZ2zHD++5nc8/9zTkSODYiUn8/uGn6IHHnsXcfAvFag+8wIcU0GtFHnwO0Go20W7M4cJzd+OnP7idr7rsLPRUijgxOonfPfI0fv27x+n46AIKfX3wcgAiNQ5CqB0CtYUaAg5x07UX4R/+9jt8zunbIASwd/8R/NMvH6YH//Q85ucbKPf2oTY7iQvP24VVq1bhT08/Dz9XRalchowjSy/fIzRjwvzcDFYPFvGdm6/kb950BVauGMT0zAKefuEt/OHhZ+mzr04qM69QVHnZ1VIZIIQ6Q3FhDj15wvVXno87rr+ct6xbCeYY73y8Hw8+9jK98eF+cJBHqVSAgNfV+e15XnK4iCOwsvwPIElpDVaZnwVBCsW/nkZdZi8nWKV6gVHCpExJyYSwEUHEdZyzexOuuHAn59BGFLZQKA3gzQ++oJfe+Ry5clVvaBfwvQBRGGLj8h5cdckW9uIWJuYknn7tU4q4gNiLQOyB2xKDFcY1l+xkkk34QR4vv3+Qjky0kM8VIThEpA/z6OavSgkO6H2pUrmOEp+VSjtjhJgxla3/Tx/RlbZ8yJqNWVO8Q1C6JnNxeCvMlhwTs+Iip8WcY4v5XWylIoGXJkYL6JTcnPrkCDHK+m5UwJ1kgIWHKGzh+svOwrWXncdhu4FaW+Aff/EHmq61kcsVLMMBsYb0ds5Dnd/mIWrHCJsL2LF9I75x+fm8acMqeEKi1WrB83OoVPrx6d6DeOrZV+nAoVH4uQIKxbzjYJeInaUEK8AcqG+dqxkzDxkaar9waqUJZlwIgJCQktBohIijJk7buAr33H49X3PFORgcKOP4qXk8/9LbuP+hp+jg0VEE1R4UghxIxoCUCut6PtqtFlpzM9i4fgV+fO9dfNM1l2DZcAXTc/N46rm38YvfPkGffXkMhUoJQS5Q7YIRsAL1eg1xs44Lz9mB//af7uarLz8fxVyA0YlZ/O7RZ/Bv9z1KR05MolztRy4QCGtz+K8/vpv/9//LDyFZ4onnXsc//eoRevu9PciVqsiXipBxGxTriSKAerOBZqOBLauX4Z7bLuVbrrsIQ4NDGB2bxcOPvYA/PPYinZiuo9Lbp47oiiOwSvYOJoEojFFfmMVIXxHfvP5yvvHKC7Fx9TLM1+t4+8O9eODxV+njL44DXoBSuQDyBAQrB39HxlFznDpzV4GVuE0VgymTSN0XOn+8nbQsNepSx3zFUqLdaiJuNbFhxRCuuGAHb14/hEZ9DiwlcqVevPfJIXrmlY+Qr/RrPlAxih758GUDt119Ng9UJHy/ilffP0B7D40jyBchIRFHjIIncf2lO7k314Dn5fDZgUl678ApIF+GYCVUY8NjVvOqP27KY2XgKr7Vp9ElQsYgLEMTaVLkOUIvi5Qchb2YwHJ/swKrNLytQ/gsFjSWPWAie7kFAzBnMqSf5U7pbZ/Rcz+RyskzUhNUpX9RIQuyVcO937mFt21ahTiOMDqxgF/+5o9UDxlBrqTzSaczR9i2Ob82Gy14JHDmrq24/OIzeeP65Qh8gVarjXyugFh6eOeDvfTia+/i6KkZCOEj8AN4gYDkGEwSLA1x7SgAzBYqx85yk+hKP2U22gHSgxWRRBSGCBsteIiwfu1y3HztpXzd5edh7cpBTM+38OzL7+O3Dz9JXx4+Ab/Qow4ElbFmCgIJZY415qaxbKCCu791Hd9169XYsHoEtXoTr7z5Mf7tV4/SWx/tBfI5lCs9+jAGvVAghDL/Zmdw2uZV+Icf3sXfvOFy9PYXMbfQwp//8jr+xy8epD2fH0KuWkWhkFcHDRKBY4kzd2zET793A996zaUY6O3F2MQcHnjkL/gf//4H+uLQCVR6+xF4PiKOzeBACKBZryOMQ5y9cxN+/K0b+MoLdiFX8PHFwXH88fGX6LFnX8V0rYFytRdCeAntEYGFj3YYI27WsGbZAO666Wq+9rJdWDZYxOx8jFff+Rx/fv51+vzLE2iEHvLlAgKPVGoWJMvv3Uwj9zMr5k18M2T8ispLqWionheeBwlCHMYIWy2wjLF6pIzzT9/COzavQYAYjUYdnsfwciW8+cF+evHtz0CFXuQ8T/G/2vWNsFnHeTvW4+Iz17OMmpiY9/Dkyx9SW+Thez44iuAjwlUX7eKV/R7AIY6P1/Hiu/sJ/9/O3vzbs+OoE/xE3vvd3lbbq33RUlVaLUu2kQy28QB2YwOmwWzT9MDp7pk+03PO/Dnzy8yh5zQzwHgYMNDgpukGbGMBtrxqsXaVqlSSal/f9n3f5WbMDxmRGZn3fkumr616790ll8jIiE9ERkYO92Yro44oZVJy3fMzmzsdCCz+TiK4rfDjsKKZ5l7uwy3pXAqv7P7SwYfDdCnMQHtPr9JvteidWI4xS4MJqYgh9wOUaCqmrgHiqqLXYEx5QhRs/n49xa9/8XP8wMnDgAeu3tjA737py7S502A4XNFCWsRlIDJTWMGsMZ1N0auBx86ewtNPPcaPnD2BldEQPPeo+0Nsbk/ww1ffoOe+9zLePP8+JrMGXBGqXoWqqlE5YSpugkmMlLbEi/kRkBRFtKcHS+pgEwhN02Amx9X7Zhf71kZ48tEz+JlPfYyf+ehjWF/fj7sbW3j+h2/ij/78b+lb33sF1XAJg+VRoI33YXXTEeYcDondN6rxiz/7k/gffuMX+OHTJzBv5vjBy6/jP3zpP9Fff/3bmM8JK2t70CD4hxwFQTefNxhvbODggVX829/6Ff5X/+ILOHb0ACbTGZ773iv43/7DH9F//fvvgeoR1pZX4JsGVmYTCDvjMXyzi3/2yafwv/6b3+BPPvNhDEcDvPX2u/j3//eX8Qd/9Jd0c3OK5b17MOiHfZ4gGXvXx87mFnqY4NPPPI7f/KXP8BOPPghHFX746tv4gy//FX39W89j6oYYre5FTcH94CgcXeWqGtPpFJPxNp44ewz//LMf52c+/BDWD+zF7c1tvPTyW3j2uZfo+69ewPW7YzDV6PVq9Pt99Oq6pZzt3CgzCsQ5IFlFdF+oZx/HtJnPsGfUw5lTh/HUYw/yAycPo+88drY3MJvN0Bv0sDsj/N03f0g/eOVdVKMVUBVSw3jqgQmYjbdw8vAqPv9TT3LPT8AY4D994yW6tDFD3e+DZh49v4PPfupJPnloBIBx+dYMf/edV2mKIaiqEbfHaJuTXyPtm0TbmlIFZq9FAi4XQEYuSD0qsMLJP2FedJWRlaMHqWqTgrvHwmI2PprgS2Gf+2s0fgpAC2FlAtCLT8psOLVLyzFqnAF2yfbXSa9OP33XkcN4PMZS3+G//5Wfx30n19kR4fqNLfz+l/6Mbm3PMFxaCkKCKjjHCHG/IXVvIoZuGwjBf5PdXTh4HD96AI8/chpPPnKGjx7ai6WlAVzfYTye4t33ruGNN96h8+9exvmLl3B3cxdzz0BFqHpBeFXOyZYMimaANX299Nf7BvP5PKRsYUavX+PA3mU8/OBJPPHYaf7Yhx/BQ2dOYWk4wo0bd/HNH7yIv/rqt+i7L57DlAkryyMQA40EEdZUgT1ha7yJPmb42Z96Br/1G7/IH3nyUfR6FS5eeA+//4dfoT/6y2dxd7vBcHUJdd2A5x7EtYafYefuBgaVxxe/8Bn823/9a/yhsydRO+C185fxO7//Z/RHX/kGdnanWNm3X1AhQEWmVl1ha7zH1t2b6NfAr/3Cp/G//Otf5yceOQ1PhB/88E38n7/35/SVv3kWu9zD6uoayDeY+ZDPvSKgYY+7m5tYHVb4uU88hV/5+U/zmQdPoPGE7zz/Ov7wL75Gz734JqrRKoajYO4Qi3PeBR/XeLyLZjLGmRP78N/9+If4kx97DCeOh21E712+g5ffeBevvXmRXr9wCVdvbWF3NoNHhbruo64kirzSbAfOmI+yMsaQMCCG9+HwDOIGw9ph7+oyTh0/iAdOHOSzD57CgdUh/GwbO7tTNPM5anj0hku4emsT//Gr36V33ruJ4fJaOOuSPSoQvOtjOp1g74Dxxc//OC/3d9Grl/EP33mVvvf6JfTXDmC6u4O1PuMzP/FhPrY+QIUGl29N8NXvvE4THqBX90OKaN+BXij51hb5k/QqhVYpXLreKwFDCgkiIwe6fVqxnaODZ01BBPhi93th0wfB05a8WcHRrZNLZuYk/Lr8WfFJg+AkLgQWAKj+ZoTJ4EHw8ykGNeNXfvGz/MiDJ+A9487mBF/607+i96/fwWi4Aud6Acnp1o0iJ7TtTyAyYTJrMJ9uY9R3OH54HWdPn8TpB47zkcMHsL5vD4aDHmbTGW7d3sC7l27g/HvX6PLVm7h+4xa2dsaYzBiTeTjZl6H7JBU+MIa9GqN+jaWBw/49qzh6cC8eOHGET5++D/edOopDh/aiAnDn7hhvnn8f333pDXr+h2/gzXcuwVMPo6VlGY85KnJoyGE+n2Oys40aczz95EP4rV//An/ymQ9jZTTE9Ru38Od//ff43T/5a7p8fQtLo7Afs2masHIoe882t+6C5zv46U98FP/uX/0af/KZJ1C7CpeuB4f87/7hX9L161tY2rcXdS+cfs2izMK5jUUmSg6+ROdUcN3B/r3L+B//xS/yb//6F/DgqaOYTmf423/4Hn7n9/+Mvv7NF0D1EMvLSyLig1Z2jrDrG2xv7+LoviX88k8/w1/8uU/i5LHD2Bl7fP25l/Dlv/wavfjm+5E+DoBjD/g5uAopdSY722imYxw9uA9PPf4APv7UGX74weNY378XDIdbd7bx/tVbOH/hIi68f4MuXrqOm3fuYnsyx2TuMZv7gAI5IAdmD3aE2jn0HTDoV1ga9HB4fQ0njh7AmVNH+L7jB7C+bx/8HLh56ya2d7bC0fM+vN8Q8OIb7+Nr//Aa3Zl41P1eWA0lh6bxgOtjPt7C/iWHL3z247xvmdAfDPD9V96hv//u66DhGnZ3Jziw0sfnP/0kr686VK7Bu1d38Hfffo0mbglVbwjHLIeVtIXJIn911+/3ipWyY6857MoFNwZa+4jVH1QiNuvHoqVDD+Ut5ISYrMCyFXqfp0cNqCtHTzFroanY+gVQNCrrvBFYmX0N2eKmgoUIcx9s+vlkih4RPvNTH8ePf/QR7leE6bzCf/n6c/Tt519Gr7+MqjcIecOhEj2hnfagcDiFhxnz+RzT6RR+sgtUFfbv3Y/7Th7ByRMHcP/Jo3zs4DrWD6xhZXkZFdWYTKfhv8kcOzsTjHen2J1Pwx49hI2wg34fB/buwZ49K1hZGmJtdQnD0RDzZo7Nu5u4dOUGXnnzAt449w69+uY7uHj5BubjGeqlZQxHS9DzUbwjNARMp1PMJzMs9wnPPPkQfv2XfpY/+fSHsbI2xOVrN/HVb3wPv/f/foXefPt99Fb3YrS8DG5mYDQAV3Cuxmwywe7uBn7s8TP4t7/1q/xTn/oIVpdHuLs5xl/8l2fx7//gj+mNt95HvbwPw8EA3gUfDZjCCioxWPw2kV+YZQNxMucr57C9O8FsZwOPnT2Jf/Obv8Q//7M/gcP79uDu3W38169/B//H7/0JvfDqBaysrGEwXJZ8ZQBcBfQIs9kEk50xzhw/hF/7uU/xZz7xIRw/ehA37uziG//wPP7ya9+kF958D+MZY9AfoO73winTMuyVqzCZeuxMtjCogROHDuCR0ydx5r7D/OCJQzhyYA0rq8twzmE6nWJrZxfbkwm2d3Zx5+4Wdsa7mM9DKiVHDoMeYTgaYDQYYjAaYmk4wOqoBoiwubWFS5cu4/r1G5hOG6wsj3Do0AEsLy2Bej288/4tPPvt1+jcuzeBug+qq7gI4zhkMZhMpji2d4Bf/OmneWXoQXWF5197j7723KtAbwWz8RYeuu8gfvKZR3h1MAdTjVfO3aTvvvIe5uih7vXEvxZW7rlAMpb3S1TThbQ60Zl5t2v1NVpUaiW1vo9M0lrgiL8vHXooN+u49NSj7bS2K1m6JYTDexyRVPtEDPbqMJeVhejvSsm91M+jl4s+rLwJXba198DueBsff/JhfP4zn+SlpT4qV+GlVy/QX33927h2ZwfDpSGIIP40pNN9veRrMgT2YlIo1B/2axzYuxe3NzZx88pVYDoGhstY3bsXh9b34ujhAzh88ABOHFvng/v3Ynk0xGjUx2gwCH4NabNvPJpmjsl0gt3JDNu7M9y4eRvvX71Jl67dwqVLV3Hj9ga2dqaAZ/QGQ/T7g6CtGAAazOYzTHYn8PMGVFU4cXQ/PvXMk/jcT/84f+zJR7G2sowrV2/gq//4HfzxV75KL75yHtQbYTAcgOYNAIZ3FA6LmMww3dnG2VOH8D/99hf55//ZJ3Fw/yrG4wme/c5L+N//rz+mb373VaDfx8rKilFoVaR9HIdCQ9pTrRNDh8M1w8nRO9jd2cZHHrsf/+63f5U/+6mPYm1tGZdu3MGf/PnX8aU//i90/v3bGKysoT8aQDfpVkSoqh7GuxM08108cv86fvFnnuFPP/0Ejh09hDsb23jh1bfxjW+9SD94+S1curGB3Tmj7g8wHPbRrx0q9AAEBTybzzCZTsA8x6jvsHdlgIPre3F43ypOHFrnQwf3YWVpgNWVEZaGQ/T6PeHBwNfT2RzbO2Nsbo+xub2D6zdv4/3LN+jW7TsYj3ewZ2mAsw+e4FMnD2N97z7M5sDFqzfwg1cu0KtvX8EUdTjJ2c/FctDYKMZsd4zHHjiCz336I7zUm8NTjW+9cI6e/f5b2J16jPqETz51Bh8+e5R7VYOtqce3XzxPr52/g95oNfqSw+RPc9dGs9txjMIBKWKdJdtEloulQ2DZv7NxD46+XIAxxTbpVNb9m11lAigQlpmcscKunTQMECQ7p/ipop/JJYGVOSNJ/GOcGDl2RpAOYbET3wqsbttaczM6zHYanDi8D7/w+Y/zfccPoq4HuLGxg2988/v0vRdeRcM99AeD2JdQcTCLbJu9WYhovEePHE7fdwwPPXwKB/bv4e2NMb1z8QouXrqKqzduYzyeAbOwNI5eBaorDHsVhsN+SEVLss1IckTNZw3mntF4YM6McFx4haqq0Kt7cM7Bg8NG4HmDZjaHn80AarA86uH44QP40COn8fTHnuSPPfkIThw7AgLh4vtX8NVnv4W/+Jt/pNffugKqlzBcqlGRR9MkJDyfNxhv3sWR9T34l7/28/yrX/gZ3H/iEGazBi+9fh6/8/t/Qv/5a9/CrKmwtLaaVi+L9CNxTJCPOalvJ7e+IwqTGBp4AFubW+jRHD/ziSfxP//LX+ZnnnwY/WEfF967iT/+yrP4f/7sb+ja3R0sraxK+IduH2F4T5iO55iP7+DU0RX87Kc/xp965iM488ApDAZ93Lx9F6+cew8/eOFVeuWti3j3ym3c3ZmJj6xCVTvUVR1SZMvm4WbuMZ/P4mboyjnUdY1+rx+S6cmKokMYz8ncY7q7i2YyQe0cBr0KBw+s4cx9R/Ghh0/xyaPrqCrCjTtbOPf2Fbz42jt0/tJ1zHyF/mgI6gWTWnPHk+thvjtDxWP8xMcex09+5GGuqxnG8zm+8Z236Fs/OI+6X+PsqXV8/IkH+PC+IebzKS7d2Mbff/c8Xd+cozcKJ+g4VNmqe6LdvVcE09yVrUVIAqs01+5VlnMu+KSLQ1ODzwet8joFVafAAvLNnDKD7aqBojAr0ILAkkABMfeC3yE5JUkEFncILKlMf7R8S0AQhLGJ3keCZxcDQAU4YDqdYFjX+PjHHsdPPP0471keAEQ4d+EyvvoPL9Cbb1+EqysMhkNZhg7Mz+KDYd8OhmAwJtMJelTh5PEj+NDjZ/H42VN8YO8qyNXY3tnFzZs3cfnabbp+6y5u393ArTsbuLuxia2tHUyns+DN1jxJjgBXh5/ixA17GACBoBjUfQx7FfbuGeH40f04fvQQHnnwFJ954CTuv+849u3bg3kzx+Urt/DDV17HN7/zEj33wmu4fPUOesNlDJcGgBwZ5ciBqhq7sxnGW1vYt7aCX/rcp/CbX/wsP3r2FBwRzp1/H1/647+h/+8rf4NbO1OM1lZRQ7xTZmyMVR+QtRH2GeyXT9iOpbJJkJzhOREaOOxsb2K1T/ji5z+Nf/VrP8uPnD4FMPDyWxfxB1/+W/rKXz+HzZ1dDFdW0O/3wF5isKpglk4nc+zu7uDg3hU89ej9eOaph/mJR0/j1LFDWBr0sbGxiQvvX8Hr59/DK2++S5ev3sCVm3dxZ2uM3ckMTSM8q+cqVi7EKenClLog4THsVRgNKiwNh1hf24NDB1Zx8sh+PnF4HQf3r2HP2giN97h24y7OXbyMV968SO9cvombd7YA10N/OETlHELwiZcFgj6mfo7JeIz7Du/DP/vUh/nMfSEG69KNGf7zV79Db797BafuO4off+J+fuT+w3A8x52tBs+//h698PpFzKmHXn8EzH0IZDVCoRQwXULGKpw4jo5iiE75Pkd+IP3qnvM3zfvFwmmRH8sILNlaYKAMMwNONaRpvAnRLk2zrBJXTnmKDvvUaI6cr+V4s0oZECxF5LbICajlEzuwHObaeI/JeAfHjxzEp575MD98+iSWRgNMpw1efuNtfPvFV+j8xWsg10e/HqCudR9UJb4JrY9T+eIEnUwnaOYN+v0KB/fvwYMnj4gP5DivH9qDpaUR6roH7xtMJ1Ps7IyxtbOLja0x7m5uY2c8pel0jnnjMW9kYy4Bg7rCYFBjeWnI+/ftwfr+fdi/dw3r+/di354V1HWFmWfcunMHFy5ewvOvnMPzL79Jb7z5Dm7cvAXfANXSMgb9ISrJB+XkVJnZbIrJ7i72ra3gcz/zCfzmr3yOn3j0flQEXLt1F1/+i7/F7/3hf6J3r25gsLIC16uC+QWJtqdgzqElynU8nMjixf4P5R+iKvpciQiNnNrtqMZs7rE73saJAyv4jS/8NP/y5z6Bk8fX0XjG8z98G1/606/SV7/1IrZ3PephD4NBQKPEirIJ07nH7s4uyO9i/54hHjxxBB966AF+/OxJ3H/qCPbtXcPScICmYWxubuPu3Q3c3Rrj9sYObt/ZwNbOGLvTORpO6bdr5zAY9LFneRl71paxsjTEytIAK8tDDPt9gBi7kxnu3t3Be1du4cKl6zj/7hW6ePkmbm9OMGsY/X6FXr8W94NaFoEQ81kw8/cuD/D0U6fxzEdO897VZYzHHt/63qv0jeeex4GDB/GJjz7CD99/CMNBjZ2dCd585yq+9+q7dPXuLupeH7UT/pU05UyAryjmGJPlXADJgrHCLP6dx6e0hByATBjquxWSjUeUA5ls7poN0eV8XnSPRgfPxjaBETbEmstH1GEK4LwQ66S3HRYbLwxK+cxcJXN7MyG6JHR5pfJC2zgenCXO1ckM3s/wwKkj+OiHH8XDp0/w6soA490p3jp/CT948Q26cPEKtnam6A+XUfX74TDPgBnMFiSOJ/Yks7HCfN5gNhmDmwkGvRqrqyOsH9iHI+v7sb5/L44cWuejR/Zh755VrK0sY3V5iOFoiKo/QF05VKK9NCaLPWPuPSa7U2yOd4JP5PptXHz/Cq5eu0nvXbmBi5ev49qtTeyOZ4CrMRj00OvVCDFlaZ/afDbD7ngMP5vj+NGD+MynnsY//4Wf4SceO41Bv8a167fxt89+G7//5b+il994F72VNQz6PaAJCwRw4r8Q5B38DU2nCRGQdYdZoApPUbRP5kh8i1TUqO+mwu7UY3e8gfuP7MGvfv4n+ec/+wzuP3UI07HH8y+/jf/89efo6995AVdubKJ2IwyGI1RV4EVPBHYuIP/ZHOPJGI1vMOw77Fke4MiBNZw6dggHD+zlk0fWcfjgPqytLGO0NMJo0EevcqiIJCg4uARm8wbzpsFsOsf2eIytnQl2dia4dWcDl2/exa07Y7pyfQO37m5ha7yL6Szs+Kh6Pbi6FwS0b8TM5EBbbjCdzOAnM+xd6eMjHz6Lpz90Px89uAdb29t488Il/ON3Xqbx1ONjTz6MDz18H+9dGWI6meHCe7fxvVfP04WrG0A1QK9XAzyHpJNIAstREFiew/5CQfcloinBh43NKq2e5JtKwgwy66rCcW7nrxVs1BFEbg2sTqG1dPAheUmc0GraqU+Kip+QFBMGdQDcCnXoIkCrcgsrbYiEJYx0jjsnSMTnphxbAgDPqKoeGgYm0wkcPO4/dgg/9tSjeOjMCd6/bwXzucflq5t4+dW36NW33sGlWxto4NBzPdS1nFFYlBuEVqwQgIMnhNNNZlP4psF8NoOEjKPX62M46GF5aYS11WUsjfpYGvYxHA7Qr2tUdQXvQ3Dh7u5c0NgOtrbG2BnvYme8Cz8PQoTqCnVvgKruoVdVqFyYAIyweX3eMHZ3d+EnO1ge9fGRJx7GT336Gf7JTzyNB08eAdEc5y5cwt8++wP86V99nd48dxHUX8ZwaQlhDyilQ7xlXxyZDdhdQ2EfhLg3q1FzlBpNiDhwHH8GRz5B46A91ZjsTjHfHeO+Y/vxc595mj/3qSfxyIPHQHA49/4NPPvci/j7b75EP3zzXWzN5uj1RugP+mGVDUBNDkwMTxVmHpjOwmIFz4Niqxww6PcxGtQYDXpYXhpgNAjjVdcEB4dZM8fu7gST6RTjyRzjcVgwmTWMeePREKGq+qjrPqpejV7tUOvxWjFMyInxR/CNx3w6RgWPg3uW8dHHH8ATj5ziA/tGmEx2ce78Jbz+5nvUeOD0mfv57P1HsTwkbG5v48L7d/HS65fonSu30FAPvcFIDl4NCQIIOkeTmvCUsJzOqTRs3SFGcUdG8cy6Y+zsDrfaJmFAWeXfwbXkVJBFvkjgxREBxWohLR16CExB8mp3uqLd42GcRCEYEAXc9+0cOGUZAFpEudeV2a8d3xEld08kXiEgbXZChb+7szmI5ziyvoYnHzuDJx47y6eOHcOg38PG1jbOvXsJL77yFr19/hLubu1gPPVoqEa/qtCvODqdWZzGkAHRVVLHLAMRaOCZxbQI/jfmkNtLszxGYUgkMXAOzjlU4giunB7HpDTwwnwO7BtM51OMG4AnE8BPsLa6hLOn78OPfeQR/uSPPYUnHjmN1eU+bty5g+dfOYevff179I3nXsDlq9dBSytYGi6lsSUXfEKt8epON7Jw7GSqkET/c0Takr45Cr9Ci0qIBKv5KcfOgypMpmOMdzZxdN8KPvHUw/ipTz7BTz1xBuv792F7p8Hrb72HZ5/7Af7x+6/RO+9fw3jmgXqI/nCEflWhrquAmrR9WiUzfDiNBnM5hZqZw1gIGjKeC9SuQiXnZDr5GZ454QWhVQU4V0dDYz6bYzqboaIGB9YGePDUETx++iSfPnUQo0GF6W4ImXj34lVM53OcOHkUx44ehG+muHJrA2+9fZVeO3cFl29voHE1Bv0R6spO6JC5Iszz7sBOGZxMrCwSWPn4o/OdLr9YV0iDiiUUVRDlkfMhnCPNWT1cVVfwaXTwNEJmUA7BlGYHuw6m8FGcmIp8oiDiAOa10HJPof5dbv/pQmBdV8jV076v0t8KLDLPNEYI0EUAeSrHa80mEzSzOdZWV3D6geN46vGzOH3fET5y+ADqqsKt2xt4572reOPtd+nchUu4fO0mtsdjzOcezvVQVz24qoKrK5nwCFk3O1JQ6NYigtr1AHzOKEHgiXPcI0xcOctAzW7PHjNZYeR5iKQeDSscPbQPj5x9AE8+dpafeuIhnD19P9ZWlrC1tYFX3ziPZ7/5Av7umz+g1y68h/nEo1pexaCnJ1wLgzjpR4fA0hAGe/9HGTvnFDGZcSOf/Z3qAMAOekiBIwY0Q4anmKe+aTy2Nm9j4BgP338En3j6Mf6Jjz2GR8/cj7179uH2xgZef+sCnn/lbfzwjYt07p3LuLk1xWQ6B7keqrqHutKDdGUMGCHWS87VhB6UQMj4FggbhnW8tP2VZiTQ/xiY+xl8M4fjBqNBH+v71nD/sQN47MwpPnV0HSvLQ8DPMZmMMZnPw+JP02AwGGI4WsLdjW289c5lvHLuHXr7vTvY2JnC9UYY9PuBhdUH5PIcaf8Un1Aap+TLKl03LaGl86kAJ127XZRuLQG2AOEpS8XoAKspANDS+tlgp6vUVSJE+xWtDsjSYAAFoUWtZHSlwCoZXFcJu4PUbGfLToVGBfNHvF2WcLY+MIidoAaD8lSCC2z2PjjRawD715bx4P3H8dCDJ3HmvqO8fmgfBoMBJpMprt28gyvXbuG9S9fo2o27uHzlJu5ubmFnMglmAYctIERh6b+ua9meUxnmb+SoOIbEvAYBhXCv4WBeswe48Zg3jKYJCfequsJwOMTe1WUcObgfD95/FGfuP8qPPvQAzt53DAcPHoBzhNt3NvD22+/iue//EN/8/kv00usXsLG5C+oNMBwO4WpRLpxoyeC4B441Ri0KKUppzRb4Icv7nYGDUCHgYsgIxW/MJGB735QtiDUAGYJvgMlkF9PZLlZHPTz8wGH82BNn+Cd+7Ak8evY09q4to5l7XLlxG+cuXserb5zDxSvX6dy7V3D95ha2tyeYTGeYcUDGvapGXVVwVR3pUmnWEe2LKHZC2ArluUHjPXwD+KYBcYPaMZaXRtizsoTjh/fh5NH9/MDJwziyvg/LwwHADSaTCebzBq6q0K8CyvBEGO/OcOnqbbx24RK9cfEqrt3chmeHfn8EVztBnXkywS6rphyjzFpZEIbQEiKcgw2iNG8jZjJ56m355ck7neWHXwCkIHE9HzECD+2n8oAVWCAXnaum5MzMIgoTPTK1MFfT0ehFPirAdrzdmdxXtACWsmwhojRwIDLwXfrBeQ6rULeL/UpOdAZQo2lC6AIww9qoj6OH13H6vuN46PR9fOLYIezfv4bRaAmMsOdwe7yLu5tbuHb9NjY3x7SxuYNrN+/g5q07uLu1g53JDLvTOeYzj2Y+RyMmB8BgDmfHEREqCrFAYeNtjdGwh+XlIQ7sP4ATx47h+JF1Pn70EE4eP4pjh8PK4dLyEsANtrY2ceXSTfzwtbfwwivn6PlXz+Hti5ewsbkD1DWGoyXUvWCaeA3eRSCLMkdcydExJUJENyBBRYm2pQL6IHPC3uN4QG68WygpQceJa7WRGQ949vEU46YBJpMdTKfbWFka4YETh/Hhh0/hyUfu4ycePY0Thw5ibU/YDL+zvYtbdzZx+cZtvHf5Gi5dvY1L127R+5eu4cbNO9jYGWN3xpg0jHnTRMsBCIq46jn0ezVGvT6WRgOM+gPsWR3i4IG92Lc24gNryzi8vg+ry30Mh8GX1symaJq5mGzBL8ZNg62dCW5v7uLilRu4eO0OvXvlJm7emWDqGVW/h37dQ62ohiXWzVHk33sJnYV/E2Uz4l4CK7/PorjUdaDmW1sgdpmkduwCsEAMmfLiNyX7LYctXxlqVIGFKLByR1pnpXLMOHsf87xHH1eHLavLwmaqhNCF0AOkH6pRxUmppoqhbqbBxSmsZUTTkI0z3lP7Wyohq+ZBqiRnNQPwmHtgujuFn83Q7xFWV0Y4duQIDh/ah5PHD+PE8cN8ZH0fDu7fj9XVZfQEUXl2mMznmE52Md7dxc7OGJvjCaaTCebzEMbgfTjhpK4q1HUPg34fS0sjrK6MsLqygqWlEZZGQ4xGw5g1YDqbYHNzEzdvbuDS1Zs4d+F9nH/vMp2/8D4uXrmGrc0JZnNG3a/R6wenPPk5WI6AgqsyJte+658xO2RkABd/qhmXkJR1wrcFU8YvxYTg5PqFkUKRN0QfFXxIckKN1KnJwyR1dwUCVRUaEPxsgulsivm8Qb9iLPUrHDt8AGfuP4YHThzis/edxImjh7C+fw0rK0vo1RXq2mEynWF7e4Kd8Rg7Om7buxhPZ/C+ATOH4NE6rMgO+wP0e2HMB30VBsBcFlzmswaTySysIs/n2Nwe4+72GLfvbuPKtdt06/YmLt24g9vbU0zmDLgKg16NqhoiZGOZC4UqaJJuMnSKPxYJHOQmYvZMibwAOCgfZN+aOMW0X1Tc5R0orwu4tK0p+V0i6WOdOn2FV2JZy+tnY2GMBuwY4Fq4N2asyQkixPBRYKUDJlhQD5lvdF9hkLwA6/YfuJhPviS4oVKLmF1XqCctq8ed4Opm4zYCzHxr4r/JnPakPrvQr/l8hvlshqYJJw33ej2MhiPs27OK/XtXsb5/BQcP7MGBPXt4z9oaVldGWFtbwcrSCEujPnq9HqoqRLIrGgQRvJh9u9MZtsa72NrexsbGDra2d3Dr9l1cu36Lrt+8gzub27izsYVbdzexszsJJ7VTDVf3MBgOUNe1dhaKhljMHeeCGUaxa20mbqNgMaeRm9rpmx/B/7gQRWsd3e/CuieUWZ1LW32AmHpI/0bU3oIEq7AnbzabhVQ98xm4maFXOYyGfezbs4J9a8vYuzbC+v41HDm4nw/u24PV5aWwijvoYzjoo9+vUdV1UrBNcNB7Zszmc8zmDcaTGTa3d7A9nmBnd4rNrR3curtJt+5sYmNrFxtbu9jc3sFk1mAya0IwatXDoNdDXVWoKrPpRSSNTtzwe5X4V2ez5WcgggfAuGQop5MWH+GA0rxESii21nF0B6f3CMlfS4n+9upMelhcVq6U/NDi0+X1s8IQAGOeBBbIMKTVyGmVjBCc9cw5aomMH2M91Icl8SdwUWBBtkNYuG+alzX+Xs5AQJ3WqsXlu/wMs/CsIAqLL6eEsdHPIuiPxYRULcfMmHsWjTqFrihVHFb5XOXQ6/fQ6/Ux6NdBYLkqlsEUNo17HybVZDrFeDzGdDbDrJnHVD/BaVPB1T30+n1UVYVa/E1O2uH1QIXctpJVVLuUnPe9i75MlQG2+oF1uqvu9h/MhMXfpblgg4SzSyZpV1lFwWigpmExzjpREM5pDH0L/Oa9x3we9nQ2En5C7EO2ZXKCfCsM+r2AnKsqpocmNIICg4IMexE95vM5ZvN5VBSAA+mijKtRVS6Ydy7tK7U0VkGUZe+UPjJTa3eHJnnMlLGWFIVAB8mcSU8cxHvcEqT0Njgu8VUCZZHP1P8qf3SO1UJzVcpJyJuzPO9dpmUQWFDHqwc7H/0+SWB126NR0yEttFuIHyy25BhkOchBJ38YoDgzDOG1g+ndzg7L37pVB6TRO/ZUtKCprfZiEaLWRA0CK7y7CDeE9ik0j3ej9osmrKC3sDAQ2uS9D6EM+pU5ul4RaVVVca+epphWahAopPCFCsuQ0sSDZcNo9zJ2QFgQDWlo2UHP2CNZ2SNwCmEh6wuMvWgldewusphY2WRMbbV0loYsngBpOSmc9syp8tLkUDCiPBczghLJKTDK77Kaa+S6ngOQ9bHoF7kQ/FtJQkjn9EAwfS1YGGHDvTiplVjUjlGiqHdSf7wVJtInB6AUWCxoSH1L0sqMdtbfHPOwF1ZU7hqQMlzbxCSkhbAwnbuFkx03MugP8Xu0aNH1fR0Egt6ojLcppM5QTRqlthybkTGY6bh1eLMeEMCa4I/NSbmhsdap3taQoXTVAl1XvgJJhgjanqQZMqJR7niMXjWq5HxSznamG7IJbRiyFh6DbeMyt7bLheDBEO5QgytEEziAOgPRI2oLA6jHvUfqkwVQhbDtOsnDtjjKF85j1ggorbo0Biqo7N/tMWivAJfvUBzH+I35XZFqR6sXI0Br2lBCJl0LPWoucexw2Fun1A2CTja5Sn4rADFMIK4SmjYlUyXtoaxErbDnoFhc4lmKE9G4GKCqJ/EjWAVAxzwQqauCNqDnZAGp6Q+YMB8BFFWpDFwCE4CwcdfYylhVxl+VAEniP06FtPhBaRW5WYBLeCh+0FRk7LAirSjYpe3pkDBxNBM7yEYRW0TqrOmOHTz1Cel7Koi6lrs/WCOXhDPMXjB3Pric/cbMAvWR/Vd+r6jOexVE7TYktGdvapuSQ1oRjWZMncNjDg7ZQCkcXEHMEvcGRGpn8sBMCgOR21qH83qj78rS13wP5HUWmjcV20a094q5SjzgC6Gi5XTUYcrNBV7eBvsdlbQo+O5e5duyWsv6xbdpgsU7KJVrVJDSwUwhCj+ZVsCG6xARyrjEUmCkPnXQxPzsGhaCBCjL7+xz/qwYIR0UhzCaecf8SspXkJaxGuSFfMwi6OkeA0/h0D9P8p+tK5MbnI1riehqckpQCBKRwDkhSOdJzRxBbbqVDrlVMokm0D8JiimNnDaoAXFQyTxTOV7mVeq6IsgqmSrHttlkSAOkCFJMVbP0TjLTSaRKRAXeoJycPGHANakhB6QS06woecz7yTlgyxHt0+qzaH1zhmRaQaPW65GxClTJXXTgNEAJM5FJM2TRkQT3xbQhFq27VJZ2mVnibIwjN1Qal7fjQkjHJCoFV9n+LpeBFVClUk352ADNv95VXsoOkrfFpktpl2nbo2gsb3cmPJH6n1/hWwHzgR3kHU/BjRF3mCgjCdkVQQWTWWYsB77UvFNpqhuzEojhSkxAozYqe7EmcjDSdUZpBlAAORhbnE9Sr2dpl6UDq3pI7dO9vETKcZFcqtml2Z2yIWwtYW8KzWhsBkmFWKSKPieVQFErW43cVVqXhi/RWvEwCofgzAtazEsMlGYd0Jgo28SgcW3tqS2BfdIEVZplk8p0RVnRcdgUqt4N68vRiU1E6Xw35hYa7KJM4R5NTxcIdlvkvWhnzjRBEESyMGM1SnGFSa1L3vJdZ8vJ0Cdvi5pa91JMsZxFfSwRl0E23d/k8WX/5KuYrLkvVpFZ7o8r0UV55Uq3g+QiwDwzvDUOOUXPgcNKJgs/AcgBSEfd1lWiEUGsaEqe5X1s98EqBzVLw2nhQVg6/VsUmFMU541QNQLW0qrudIR2ESzTaLlULGF9BivNcVH6LLP/Zbm96kByZKAYISfMYsYyMNkiCrnniASOyt+qEeO/HYipAIv6i3NkkGWbfhbiUpKCiQ6gDBHGjrbqX+zHa9M1fVO+A4RV3fg7ZCXUuWg2ZGOTEU8VjfWcFG00yi63FhJcC9o5Iajof8pMWTL/tuso+6/lL0I/ik660I0tO5l5OR9bHrfvW+ooUizLtkKwq4yuZ1kqceRjHMUXQZR9KMtTWPZyEiqkVgCR7k8VfpRDUK2Jo2Ni2xFUFqNS1JN2LLXa34XUAWRo05oTnkSwMsJhy4bXWsJQ/xP0Wme2O5DiltBuHMybZWNLyK2FxD1BxSDECuUKzxWhdAgNW/sCYUWE6DCP5oCeGB06EVZbIu4M+9ZAJAdcysYADaa0jCLlkCG8lknlSpk8DwI5fOAQcq/rN8HdqBFOqZcMH9LrOBEmage4hFQVDdjLCWqxmrBFn4KOjHwy5n0gwPuIDOLmq0IQtSegjoUsILB+FP6TENY4JrqeGw5HkPs6/q7c8EWhp1RMDM7fCYkYE/r0bFGxpV1SkpoAFbp7Qu930KeT/wrhs2g/XRLs1Lof2tFlUkqZofKkNHXF0R5jJ6ROY8M5fUiWlxL2QOVcXDkkCgeFOCI4b6ciRbpn/ZfxdZTH+bFYTxaxWaEFg9R1tLQPGa1VmAkiqzso376FXCDZlYy2g7L9TdcAqRaEsWmzzpmO/+gwvZySthyr+bwCUfmK4nIwA7LXT8uiWHZc65FyPHM4/+4eV4Y2OSEqskXbvsqgh9N0tTcUmTDU30ajpcCMtIf5+QGBnm06x9oXjnGO5PQbFeABlSVGT9oyrzMoDPUjytRFMkvzNmW6s2hYagME8YQAyAY5StLmKa30Zjqpu3hGgi7vgZK0P8wh+0PYNdEWSqVy0HulVaOCryvDLmtbc1QRVtdycinVMiKRqcd7H/NVxXvMclQasoR/bROWBTX5qCyzpxGxGZTNHadod1gECnKUjmAEgZUIaXqYk9OYAeVElqesUzqv+F5aSeNV5r4xZWsb8vcTU7UeLbwy4pK2J5QRNpEmP411BHt9CVVCffqeYVBtbzjjrV1vHCjIRm2zbL640WhRoQScWbcUlRTjFn0IlFACF28tFETWZFgoqjqa3nq1XJoRmrGht1wxRaIWQm1hlWHRjgkPyFjofjcYBJehMuOLKRqvylgnmG+a4PeRk6y7eDqUQxEFqYpqOEUn2j6UAtsKtEUCkYtBD0pPeui9mNba43vPvdh3ETDMMn8LUGGFFAPRQR7fMT3LFkmKOhnJR6hXNNnNGKgQK0GOdbrXLYlp06AgHLEeGyuTyXeYhGEBjaMFo5K3rYELFqYU5JaESa6xTLPi74xuaV5qAv2XFDWF9dzwO2kcTb5P7oOuLk2pq2IqJEqhFpiZ1GbVyDZ5Fn4G/1oYyIyOQJRadg+faREsXfXINd1uEZ2nQNoJIEiuS/arXynUp/STnO4fIMA0jizWqJPB9MGat9oWzkwoMSc8FYwPgLuj63NXhPQbYXEl0DeE7AQTXoRL1AwqJIGGmlxo+cAyKj69RWGGDzRiv0HO7z5G4Yd6FNeX/qvyupfZqOanR5rcEX23EGeOGG198cAYF3YqqhCJKEsFoPxdyb5NK4Rj2im2cYtJOS5Coxa5WqRn3y37AAB1rma5xY+a7oEFbsaJZsxDlaCxAiCaWPZSxGils9W0XeafRRu2I6WGLjtqCWKFhjp8WZdZnZp0XeZHXqa2h6TcJPgkrTOl+51tKX5v1wMQZINy1Ji6BqQCVlY4jRmTUwqpHdIWHeJMQC3Q6FIogBxNADppOluetaHUkCjoYIvoHHODZLqep/JDnZ0+uEwYcKYUFVFkjn9tvtH4ijLieP8TLquwrD9GFxdawkpRjEEVpdNaBalnjtvGgBTkutB9kilvK7jkp/cxF7+9Sr9zEkIQ8GJdDmZukq1jsQndZRrHsdW/i67U4U7S9ErmOIYc0EmKDk6+FZb/gRIzpJrbWoTkFMvc9OyYzHGwDdRUJWhSqnZ1msqfDBOupBPISvlUfi48U6U59DfFKCM6BjlJfMjq9E2TXru0CKI7Mzra39gjEoaUtDAy/YLmp/A769YULUYmKaUTAoyGtfTO6eJlrJOpW6CZrA7TgWjmJhMwQ58ttsvH3Po+MuFuRzN2QOgg4E1j49gQrAuxeOUfRSNGeqv5F46uS1t3VGBZVdYS7QWPl6cpl24J3zGBg26iOGecKBxd3dOxjO1mHza0VwH1Npz8gw3Ux1z0zcxfUsQX/hCy5krW9kX7qEIyhZRTMEcpBdVaB7otT+nRpYiy+ZVP0RZf19IrFZk57GfLQGlyxxWjjJ8K/1UqJb8sEChQWBpMFQxGo5cE7iIIDJNn30nfogCSVRXzbQlftewuh2qkEVEogxvRUE53KMT3k8/Kt8uL1VumTtIraC5OKk3MLe8YzotbmnRTUYcQAIdtGKwQvcOjImNOOoFJEUtGChGYbKRrEk+5eZfMiqgQ7OSxdRsad/FKMpU1DELSAKGHEBfWAJITi6Pg7eA8CrnuyWoG+5hIUjKL0JKyory4B7hahJhLoZn2u1LUEYxknubvyxxQBUIUk+l5MwZzg4B0+5Z+rkqAYl2prd5ygirhDnRqFVaGmlX6a/ApByARjxlcgJq6/FMZrYwcyfjUKPo6MmqCMBndNF+SvhcgrUmABwA+99tYJJFr6Bz2anVWE4d67P7DQlMZbXzvSyQ9WZgpmiBOlsga2UQECM4FJi+JHjWeMXdIU+vGKlPgpL3sRLaoYpFZlPqhS9fJQZqUS1vwx3sdq4IlyrN1p8RpKb5nkZkRSKHlW6XRwiDZmIW+t+OauttJpnQp2SFuAneOswUJHR8uViki4jD8V9IhQ1Wx5Ub7WNRyDzPVmnLWpOqi9yKfafzOlB12SlBCHjL/oi+yqz3hxVSG1K1paIiUOiljcK5scn5J85SSYlM6eY57FGHKKuljBZe+Y0FRWV9pSdVhf5tD3DYjm5tVQ6tTTcV0TOar0BHyPsxKTHTcl0xgiExq3gRkEv1hngFXEMwIGTL3NJ1F3kmkupS8GVMD6vLW2AIdWOY8VodEYCe+NVpaNB45hKVkFoGI7ivOIdVOLBrWMnOkR4GCmAFqEGKQnDhukwfGcUC9pSyPApooxjllmhgwY43FW43U5OBIsqJTC/rMImjjR4JOY9aO0MpkkiV0FD6RCSGryKERxuQmyFYRpSHH18p2lOPiSJ3faRzk7dRO5Iojmj2mMJfxT7EQVax6BZcBG3KIMpKEAGQmfOCtcv4Ex7Y3SktbrEKrC9llRGGOzvTAH2kFzn57L8XGLCE9oJgxxAmf0oJvugRgeXkxdW1bSprWbJmkE/uyDKiLDGpXkRDvGP9OwR252ZammqOw4Rgujh0AZYgCtqfmdJbbdXExsGW/tHdSqzVsUr2UGDW/397iECYeoStyQb9UgZvEb/5WBy6DLs2nDWUimVr9yjubUFJaQo6aWxBMAGfSfj3Fp7haE0EnbrubrfZ4r76QVK4j6zQW/5rqTRUUWf3t+lJwaBloWfBNxyTW9x1SxH1cNFlQTn5R/huzkvPePBl5XHkOUUmXcy8zoaD+rPCRdbJbNJc56Re0eFH7SsHQhY5U8NtYNRZQo9ZKrEM1XNGnsg05ctP/OLJ46FsSfHXiEjXYi6Rpos04GvRAgBWLSGIaZ7QUm0kdG65pOFpEDKMftIxRI1pNIbRyP5MSLOruDMIuuuKjloBLFebjwFEIZKqus4xUUmaCmI4ks5XjBAgkNL5ByjVplyaz/VFgbCeD4/xvlkIjGoI1WfN3c4ajuIhiydpuU/LF6BXWD4r2CsrqihC3BEzKo8P47KRD9+SIddpvxYpIBbcnsOpAaY4Zco6CXK+maWLAp/dejqW3EDihPE2qx0U7g6Dm+E7sE6mL4wPMN+UDnwsF7Yy1dCLiN+Xm9A9f6uJMlL1shJTwU/QPy/1y7nW6BFi+Uz5nam2pqtMpvqLpqMlKIDkXTne4lHMxCR/pMFKHI/IoG6uTnYpBl8Y5QVpan0Z9W8J5CZYrbeOgjfV7RRMofGyJUXQcGlOOEl4ZmIC4B0tPTImDAbukbARawbwxwR4B8ZBSS0gnPorYXoHsGkck/zGleJfS3M4YjFgcyfliCORUQD0xiDMmS+/EsVVI35L1HKLTtc/xtpRVmALZlwykk4zyiZ7tAWyZB4l3rN+TKWy/IXLhTEiDxlKGA+Wh1NjG5nXT2DWkpH2BNDb4gaDbt1SgNzIONjary7RiDtHvVYHMGwBwefyWTXUcR1eJrMpFvtfxJSKziKRR8Em0ZmZpYXIBQFVVkU5RQWvP9buiLfa5F4BALj+qXtk8zRHKUL620AsfuRiAyK3FJABhL6F1bjXR/AglOA4bKjWg0XYSgBy7bSZ4F3FLDZCJKYora4Ho0hH5Fh2bom2ZFhKHuhekw8lMGp2IqQ3OMHJMeWHq0/c6is6uMOE0/zZHjRzTy3BAURSIF1WemS95M4UegWoche8iG18v65+wd9WBkjSi6aMqRaQJGL/sMBe8IOTYVkWDpbBGPmY/qsbtRMTZtwq57PuUHMgwCAM5rZLfUJSsMXNyRYOIelUb5WZ1x7hZ5ad/u/ZCktaHYmLa+ViWqd/b6O+gUNMeyDh/pYJs9b5jHFWYwn5ntK/uEVQTdOHYEcUFERUAzlhQ0aen/WVE90kStenqQo51jG5V0gk6sQT1SGimdZVIAR3xO4XZkAiZRdrE31Uah8IK00vbl5WTr4i0rginKFbS6kuEsFJOZ1EigCxDGi3BJQMbAR1rI0UKBjUyJFVv3hQSIQBrUrEdI32vHBs7oe0dcRRRwQxEGUKwtFXeC+Grxomq5SqzGs0c+2SEvqWPvWJdWS4q2f3ACckkkzVN6HToqZaj48FhQUacozbUJLkmkAbCoH0AElskdFJeE8VhWcyKnJCq2kWBVl5WoCh/O0oHPSRt2WU15Oit9C9lzn090NWirw5EbssMSp9jAktXyQZzXY1VvUCI4S1xx0VH27xhIB1yx4kGiuJKlgGSHFIzuqRlHRvPJuTAqymYkIEZm+xqS0GjoSS2xSp66wuQeZcRXy89XCFpskR4in43i9iSTNKy7IDbXd+aI4hMvS2tKMu09rKSvosp03uNCJpgPtg+pzbnfc921HMQZ2SOKIvt63AfMnMKHjUCR890C7VynHwqXxS32QIDL5iG+XyCkPlFhSk4pAeyE08dp5AzILPJUtaH1AQdM/ZsBL4+bQCuUgYFVdGsQj0MMsFnDGZRkw0ZoMQsUeglGR0ml+MKusjkmaPpI43NaMIdE0zHR6+GTB8pJKRQXtAVXAUHJarqEmLl34G/24kFS8SXtU9j7IQuDXPaiidESfRKACLUrXFdCELMILpckaaQD4auwBsBrIRf0Ea9V6u9Gc4CEYcakmTOnO33GAiyk4PlgNKObyyU7XS8mWddGuFebek0jezAGkazzLnoKuHpIlRW9oGQNKj1aWh6kNZFeVvUp2jrtqurgWlMG1X9aflaX6G9hJvkL1l96tqLTegcm2ie0gdTrxz7VlmkzmQdN9kAT+F0YzYHNmTfcEapovyw6qy7rVjMcyBXNlk7szG1NA6rd4riWJBYuJfMwi4+7rREimfpfYM0SLKHGsSYLVIV33bNk5xO+SLGIlMuuXV0pV/6W5Sd0JgpiwGd+SRJs8KumHzuemHpKEw5HXzxo9BNrzogGGFfZ7VZQgJhAiYtrWSOQlEonucOQuQnlx08ce8GLh6M5FRPLyPeZ+Tt0/KzVS79Vyekqa80GQIqM8xrBGIX89tmxUGPkJkMgm3TIWiwQLC0DyvUkQ6N4DBOigaMdmd5MYyTHhjSqkLua+miOFgd74asHWOQn5Zm6Cpj4PVEn3sIhIhymLODEWIxAR6IQmkNdESoOd+YuG2N21L6CB+qP/GD2hU5nlIZ2WZnURQBVLaFB9Cd961Udsl10KFgWVAYCETq68lNRFt3NHG5vZWmnEOLhGsyJVMb0CZZC+3pvIN93fIfp/bbBY6oblQwa1gTtdtejlFtbkElrNNRh0pB8RgYRa4VxImtlUsBefgCOq9Fjfrg55z/m6BJdz36i6Y1AbWch22kl3wfDFkNQ1tbdZoAApEtg98z33Ec9dbwF0yjppDENclrBJMcULcdgaLms+tcsCQkj66gMTsJ7OTKvgeiLy0Gw8a23/sitP2ciZUJSTqKxrY59bqi95H8W8qTsY+QVVadQAt4xPYpTJhEBzn2NAq+lAI6pxVQKLEfAQHFvpv2qfKNisko/1JIdf29qD3275L3M0FkHfrm+y6fEsD5yUphcE1dLMrbtk+UMyMuLEX3woLx0fZJPqyg4aMPwpgkrC9knUXkrXhftU6UvJw32LcZbREhLVE0gdmi5/ZbHVirbUrnsDrAAyNZAWzLlQGMNpVqWTMxpN6uXpEMHPsGzE6W2Rf7vTIAYPoQyjLPJKTBV2klDOlRcbE5qtCMpZ3LSMIsv5trY7JjalFBPMgghYm0xscKuMhHkFxO9j4jauYu+qBT6etXRb32GCmo1llI/9RPGN4wfc9bE5Feu50dyKXg2xbSYjt/Ql+jymHOclB52XWRCR0DHLqE4wdZBvp3+U4sv3gHKFAkB18igeLBFlluM9XYmaAMI6lKNvjKgpJ3nMbAtl+vWs0s5oAoKjIaM86kYsjE0WlzbWpundRJuzLIcgTZYulvhYzO0gylqIA0DCRzJeWsVtgpAoIFVsuJGZHjWY99JZ0gaZXMABdj9ihsZiDrH2XbKVJQkotyX2EzURXHLZrM2kPWctPAZvmnNBRBPnFetzBAYrcE08mrkr/OmEOG+YJ2igKO9Jl8FHvXZcKUE74xWpmzUTH3jGYz5QX/rEF+seuW35IANU2PStQqIAApcwBMWQRI8h/kjNRGJMxoBTLHbNoE8ashbJnR53GiN9Jv8buxcnC3Mo6CBCGUSGPHPAR2IOXr0rmZjQfphue0LUavrtN8MqQkxFaBwyjSKBdj1VVOFI5K1zhAMv841aX12CsOtQwJy6CFbT5FXZK9lQDUMVhRNiE7LmJS5LeM+cloaxXyFhbqvy1Gz8MbbKNyWGqeKZciDZQyrVdxTGHg2KuGcSmGKasf2WRNjc8pGEM8OHs5CZV0I9QpxTsR4WadDmmspOyoOYSQMRC0DI+gguks46fy8slNgNk1b+uOiLfVBRUabmFGMKulraZta8EU9mFIlCGAUFkKCmQZX1fwj60bMBOOExIqr9KfpMWxLHdliMa8F3nVWR4UNCGjGeLkJFGf9/H0GaLEL2HBqkFM31IKmQV01W+lF/FDO+aBVUWpM8fTcirZMRFX0BegyKze1IAWel74zQLEk7hQpU9y3MfvGAUvC41VNjtYZoU3yNYDsgc2jEMdBskGoSU/T165WdGBsVsjn+UzgQzhE2NwN6dJJ5LTsCMDqAySE+3G8l7L/FDHtG9Ars7aEIlNFOF1gqzlYIfoaZXMZARXy1fAMD6xJOYjJQhIW5+Q3tFIdE7vapCeCm2VMKW/h6VuHYda9sWpMvFAK32OfmtICuEmI0zuzfCZr0PphhyVZDSi/Lu8QeHwgoVMYeuJnyUeioKmaHNLEcIg/+J1EgUII3gUfehERjyIg3MdZ6aAl7aFXRSaGrkt2LXORfTUtuvJNuoPVSmtaDy55VKby/IXKZjM7yU0tItpZRvLq8vs1LKUFjErsBCoS9ClZTtEYcUAUATBOn3CQK2N1ckxR7LnYyMoX4IsJXEY1PRXcs4Wnergy0zLmGT7XYPrALHp5YQO2TYUzS5QhJMAQBw2PLAGZRJilDgDweZWQYaOlUzTh5T6V1iTtU0uoopocaiG9AG5hAGTYMQI54wKJkBT6iQDJ09Xa+/5wlFOFFYXG41dUkGhm9WT3MsmYxCEyc+jk8RTnmgu/FSBrP4hofE9tHIsuJwE3iKHUI/mb8gEM/v2vUxRyKpxYbbEuIbs8lFZhVRAHTFNaloxR+TLlBZntKqwIT6YgGk3gebmpciTmaUQGp+EHesQ5QKViLLwEQ050OPZLDqxx3VZX+RC5aH0k/KDfzi5XvQ7RbsN5eOm7Y71yZRO294ST5Ttac1pw/p6HmHI/JDGk5GPPQioXVT8SUIFGJZL8QwwFiCCFBlEhkiNUa2hp/lSxwEE9vLeR19ppxQvkFxOhNzkzAhrw50NAaKZ2RIO7bJS5/MyIhpuEyb9GgWZradIH0JJAETm6dgKEUGh0cqeEJzsUVjlaCrrgdHk9l4omzJGSe/kP4nSrTbtynpSTvOoAdNLBsXbySU6mNt80MU7zLIw0oG2AGTL9l1ltdBHHMrEd+UE0v6BNM1MnDA5+lHKUb5aRhwEEqcXEj2k6tilBSt3JS1K4VD+be/Z7ThxL2OUZ+kUo8TgKcOF7q2NSClOesoUyMKxk2IzXjQ+CSaOOcrUD0ZE6ZivQBOOk4YZcRVI25wI22bOhBlS53S5WRvFbH0VpnEoJ5eUpB0JHG0GIaAVJwySBqP8jhP/atI4qwWCOE9Yx8JSQ+zAk9R6z/7KjXKXDkqJPZLJGIQQELU+8gFWkBTKz2md9u9RnBhJFgbkyQbBdFE7FZkoH9GG9rsQVKaF0g7jqesQVrG8RBZ9ECd/Z/vYtqsMuchRhqktkCPjLX1XJrntSzzByE58BVctjRfH3Yb7ZIKcUxm2Terb1FiuTB0yxzzqZCc5Ix65pb3QcWlRSwWmKadLeWSgYYFiUUYKslqUpRIwtoTQmNOMvCJK9SuqkjSKLKvDtCUI7/hi+JHNdxkn0y7PjNo7ZJN7Dl3CdyFMR2ZDnquti3EULVhtVXyiSAdG8sNoP3Gaq8nAVpJRYgCCARJeiOA0KVs+ARHHQlc1XCKo/Mue4V04Sp5A8DHXUlp1UueQCnPKC4n9IxVGVCKPMqwhncar7aU42vlStBVpdlUskkYEugfATrYDdaBDY5nEQE+t2w4TiWBlSn0pg+nItDNDBcj5Qp3TiwQUReFrC9C2VoUQ8FA1nJCD9smu3LH2JCHbmNhffUIM6IEkKtScy7qZm4so2ph8TcxhiV7tkMgz8p4qidgVg0wSxyKaeTZfShTwlMrVvb1VwVMR8cVP743ErI/LrhrHb5gzfgOF5H/svex9DS6YCkZYccpeWgrTsn4vQ6JBxCzKKnMDMQPeg6mCc2TOJdRBoxzxRKffgouyyjLwERFFeX+RT0KdxF3+K0aKpNe/9ZRezUDJnDbaWWckUOSLbyvRVJ8xB1TjdmqtiNQ4qKKGEVGUCK18oHysi30jz/JzbHXA2nUhqXmCnMgbWsDSp4qbIJijYAU8W4c2ZWXbgwhK0yihUG06KYhJvEFh5Sya1MjLyhl0IZ5KR5KpIjBtSoJbvu5gRBVOLH1K3+bflDxllUB8zmFzuFUW+k2XKZrVI43PBEEUAjkf23aE7KHJZcKwCjuMhe4UsXsEVem0TXfEv0uhVAozy9sRVZt3fJTSiqCSnFAdwBzEp+WB+JUQucsFYYgI1sgzmXq5kk8+NjCh1s2tKh1dZBpuDWoUPjGlsTJIepZQAqDHwINZNud2cVzqkKKtewWF25aklcrIlYa4SEQQ8R++QUphA4MukXaZq8xSLRq+44hkgJwhgg9XJwIhHPEulelMj05qKFuaAc6HumRCPShTTU3O1KGMkzJeSs6NlC1VKZYrCDb9yX0ciCjHmVN/k8kQrsogCesTaU+etJ8v1RnZMNaVJofSNt/HGsyaUngYLjXKTBGgKo7W5BSGsE0Nz5JC05gqpY0XYsZoGp3EOtljGcqXxewxSDRDb86BfTqkpEY4zCQu6ReHuOpP19mvVH7X71S0M1PIhXIOedPCwgKBZKEg0VZXQqPJGucSInLM+NzMRR3uSMPY1oxiqR3MYGp0L6H1KaRZqyi6RFH6Jsf3VRtCmqeHGLis0VbbKVOphg2CoT3AUTtk6EC1U+p4ikRHJF5mUrEu+UvAqwpSM0i2LSFGpNAZRBk9wDCJ91U4UXSQZgnQU9h5HEDvG7M5tUOYC9GVTuQUAXNEUaQCWgWp+ekLBrTKJNG3fS/L+qmyQLVl0bxIW2F4O3HDtbh/KYlfIaDjuHSRI9fWzBxpoI0rN/x2+XRI6tMdGLE8OxHDvoLEl0J7Jk25kgSlKj/njAJOid5kQQBRaWdCvWijHr4aag/f27kRkle2adplmSy6FjnDI2rT+aTvC3XIUzxZW8e79a1qISVPrI8LMzOMvSLHFk4hypJVAkBukxBSLhujJAjICGoLjoxl0RNTzM7JrAu+nH2buUGj2kHG9HnTKNru+m6FnNjmUTZ4iriiOckdA8ZKUGF+Qu5LaPXZIA8Dm7VObYNz6q0qQxEAxlza5KSdee7zkgLafqcMLIzBjBjlH4VvVpcKb20r4rtd9LB9XAjlzTth4i8MOw3CVX1VsOOwuOx71Wl/hpdjt1qmz6KyAv3Y3kCMixPFpSdGtS9Jc5k98206xrCS5ECwgnZR2zSmSxLbhJOnHWV8bXvYOvC0g66la6NUTCUiI6TzB8PckZx4CIq9C83lyjFfEY2ug0IwReGuvG0CcuNzIMqFuqxYQDCi1rMwVoWnkTDJJyDow4xiMrESOtFjvznAIiPB782gAFJ6Wav1KQVbWkrEDhPic4fc3MwG0CEK2LCZm+L2kcQkRrMrw8bJkmjGlaFpjDDK2xVo58GsOsShPJ4qXSn3vWdG5SrATBg1ZYLwEp8PB2IrCiaHiNLkIzmtJQZSSPsAUGM0pWFCpwlfEm1Ve7Imr9N3I2lYwmPMoaBZN/OJYgV/XM5ujav6tciUYYSvRYxRsFN8L467K5WPIFllJkJMIc1yolAZdqIs6RSCNpA+upQZVk2lLkVskHJQmGHeMMf0hKHWRsYLcaPRQkHR5a/S94nM6qUIOhcXLCwo4RgAqk8ckPmRtcwW4u1QGiUCt7ToVChaZkQ44Z0aVB4PRSiFh7VRw5DnhIqd5tQ7BlKqFH3PoKo4kQjBB9QGhO3GF235oCtIZ4rsTERhJdIKWmmbxqNpuyMyyJCUvVKepFCGFdxWc+dMkiODSqrRqHuHdopngkZaq4yKzInSOaxVq9oRmivyc6qFOR0VpXV0XAQdQ9GtPt9pEH0LwkAxZMUyFJFps520ScjE+soxXTjEVvjk5eQIR8dGm2N8NgiKyZEKP+vclYkP9VvpuBSCkVJ+N1fyWWEuhXHywSdo2somPESlQtrXF4SGF+TnkI4VayGiDiHRopqabnHO2vGSBhieYBHagRa2H91CWOdVVzvuJdDKuWivwKZiRhKhRmS/0MjyCuOlHdNmJUkeviqkbhRH4QoR7JToIZNAPf8UUUr7Ku3r2LHi2WINYx2w0lcDSwkykZvUNk/KO4TUOEK+Ykrm3/AaiWakTsZpT1CwTjgg37qTLkUUbZqk/ucmHxTMthVEZC6KkyqCwyhM5D/OhyTwc9CSaezySantzetCNlY5o95r3HKkZPseYIzNOlu+J/fI8kjhgEdCN7ZPJH4nnXyBlurH0oX8JPitEFCkovROiiX1VyPX9ftAao5NjgJMFFQUmKJkNJTB8rT+bU+RpmJcWMcv/s1xhblR5ZXNJU48YjoVy1Wrg9OcyBa4uCPZXzaGbQXVLXCNUPQMWjn0ANJqjAom1UqSOF9YN+atlqumIPPDO76oBi1UESrOt97oSppl3kVX1sGgyrKy7dlscjPm6srbJoNFiKmSK2/aK2WHaiqB4PkKkl5aW5kEz7Y5MJCLfY9aulNAWSd1ZP0WDZQxEvPnAjz1FXECBD8gtcv5b7icc8ZtuRAKxUsnXmg0R2SWlJ6TLAgJazuJAtexzSeiIqyuvucpgMLzJn6bCZICISii1G85vpPKdlzFJX12VmhaJY58kZA5hLuQoVimbOwCSLv91ppRAVUV7ygaid8CQOWSMd4hKEoahHYG/7P61rVIBoCK5GSbIJBUSBEZgQm0xkXH0PbnXnxbXtr/Ou6FYs00kJKVBZ9Wcpgn/00YoHDAIcfFsLScrN3LJ4cd0IxizDDcbxBEt+a17yXN3R7UROVYe2ojy7zRwFkjydUkjFrJFKX3ombVwnUfpLmX84EXgWeFViFcoejBIB2gczB/FIETjk6Sk4Kjxiw0c6mFtc8dV0RPsNkFOt4xWj+tsFH62TFxnORhjyLaoODE0JTxUlx8QDeNbHc6eaj1DUUFHbIiAGkjpo5HI2ElJN9HlWX+jaUlgUSCzTg9A8uWqhhMHUpwLg2Bta5Nj8AcZqr8X2jTVs7ep3ChRA8TFaBKPbXKbFym6GCP3/hEFrV4FJwJZ0nfOoSSqd/+/FHMWX2/TtqeI9wtSGMmf2h0JUn1AjG5/ESktsuYqcvmTr1tCykoEcy3LUkciZD8Dy2ehBnDKFmFCclFNozbIQxqcBE5UqwDyHkiLoNnAiQwsxcHbornEXrF8uaphRIgpqaFeivy7pCpVbqCfGKU7QtWh9aRXLahhLR5nLLSTY2UP4/kYel5hviMkIm0SRMkmmbKF/JvNkZxqkiTkWZsaR53j0j+t+UHFRLUsUWlFHzpsAoyvKkoSFwTqBBjEaHCgjMeyBoiDB55WJWUkYktH6jwDbMzJlYoKib003FQ+oqJ6+Vbe6oOEA7xdUnzhGdmxwtLmT7l686sJU31EvPbASCN5yQHPQw1+rqkKlVCpTUVBZexjjQQNyowoVsNmRQh9gMgGy+kg2SYhJhBPsRHxJN/9WWzCqWTCLADreXmppxlGTK+rsyHIYOpvhrnKCtT2VdhabwrAxlbGhFTGgylvfY1DFygjJrL6mwOq/PWpE18Ge+R+jmS5swiy5WOJbKDi/mOQB7hmM0KSOA/9hWEuBcNsj3JnhEIQBYStM8E9ZOp893rnrrY56QY1FTuFFZSrzrdyTBWw7lSUd4I32tbVHGEPjGRSfTmo0JxMk5RCBJyM0tqiKtdHWdY6gTOZQAnYQikvZnll4ZH4wJR9qwB2IOQFkXCMNj9s4UgVHpGmhgBpYKoUwCXSj8ovzCXfBSSzkl2EKS6NQ1TsqasFFL/XSjDMbLxBILwVrSezhYMJCOvh7aqQvAqt2U3RqjLMWI2BseSx8sOCosAJooLGFa467s1zAMrnLrgWoKGHfCt1ArhC0M0SBn6s80g8VIfh77XIUiz1wsE1+mrEKJ0XaoJWuVwiKxOpwnpXAtEjYGZZrJ3VdQSzoJOwiphxBP5tyK002bxNC7RyyUaUqOiNem+pVsSrPngRx8YFcenQ9JSZ9BENW9BwE7Fk1bd4rcOYV+q0k/QR0Mct39EX4gR5B90dTnsF/FVFiaIJGQDCXPesb93LRYkBRJUfTgSrNLuR6SjwcJdFkKXMIv3TU0JVTKYm0xn5bSQnnFSUEHei6A0cXLpsGQBAYq+yeg2BN6IKF7uWYGrfGZppO3lIIGMyyVHXInvddU2KZGyDkv7Op/UaTUk/N8KiYQQvHZWQEqsmwiNSM9ornEqPfzpI2HCk8IM1ffluRfU1rZxy79V/ba1UfZWB0MCyA66DDdYIGxCGqx9VyQGgLP0q2hL00UXJQY2etPIq7TgQTH0xEXUG4EiENMl6xFRlZKnUA6RqWJ7A808WAJ9OU5gu9KZpnZGyBYN4cLBF8GcMH3yiiRElUXNDlTSYSvjlC7qe4u+wagshZHJntgtE4WB5AdM93NBFuqP+0uNBVDyjR75zqx0FGRV9J99WiAor4SgG0E7cjK4p5gPC4p8oWENHCmfzw+OQiUcORb6pql1VF7ppHSaK13mXKCtLdsLGtI2JqHllB85+bJjSFPMD9cFcJok6DiMtxepRwgmuReEqv7nqN+Kg16SfAoWQSGwpAOZEGGECGAplZD2BBqHnu68zvwM7CXORYkhGsmko0i2fyGJo9AhsC/NP5X0uvpmBLfkXbWmoyWo/t7SmpSvMjLLXjmvgw94lwZWhZaSORVOrVs5E4skYQaT5gGnhLqYzCQigLxsQXJIiecSu2X1aPk+CCKrncr+plxDQJAoyecY8xxlkzdHASUGYmaQxtMRpfZxxAeZYI5vqMJo1WdqZS8TJHrFsukchW9HW9E1RuXfzHKeofqsjN7h9Hb0aSdNLDwM05+FIAgxd6aWL/950T6ViAM9hAIANHrTODUCujf7S9PEJnCVkhdGpMuMtNdV+8FxHJ1zKcgbIhA5ILrSb6bKG1AzO9G+bdUowbTVUkdEe+ndgHeC28Ub4Z+EfXg3nfwsl0o8i4mIfMZuDpXJJUUi4yzqyIXDIgYKCks1g7W5RauS5OgycCH5icI/udBBdnWuPhRaPH2am4QM1jMW4kKQbaMW1Q5nUEhrNJCMdtLSMvJoUv8jq7rICBzbGsrtFJBaq/THrvAAbYerfq9bLUDWCS3+jA6BXtKrPRm774XqKAqm8Gch/OyyGNr8CATfWOgQomK0npbcJdDRtgWIWyctCJr8I+53K4Wy3siUrIxz5lvzHnApjZH6cE0yFmFpqZDTvLGIojSVGEGZeJGKiVP1Z0LJAmgMz6VZlCma0EAknlTaWuGkZQmP2CysRHbo4juxWBVKxLIIRbE8fT/xlh5B0X0xM2hp/SSMjENIKldJPU5Goghq5ICa4iI3pW046hEhWN+AICog8yWkhgBxHx0jpMZViKsCgKk1iaToOLggbk0snfgEMxGIJSuEOvfSwChTMCRFLCVmslHGkQlE7WT3UNQnFIktDw9BRdpkq5viq8LQ+rEjig5QK9RSMsB22hGlOyHpueSPVJmZaOukE5aOPgpU26dyLFI7y/oz2JKBG+2YTAIultxb0idOx1SlmTxIPfjAq3snlCgGFYqLUocI36WvUAydnVPaPgcuxlcfZ74tsQoqU4O2wm6Pcxa1QNpD5XnK2tayUnTQVmhJkJXqjm6TbWu4EcRM6QnV9/Wuzb8W2pAbHgzEk6Is/9jeA3U+uBYNUSYtMyUYNXn4Jl9FzDV8p8Ot4HXndPIlX4GjtFpCHROhVTZE6JGPKEHIkjG1JRC3uSxpOiCueFpUVyIxIt3zZvpjzEbVdEEzWYGbDzB7FnmQ+/hC3FaKhgsmiE6E3P8XUZYIY4Bzupt3ovnLnHKIs9WAneyn3WqhmNS3lJKlhdJ0p0LVjoC2WQKoVaZFCWEVMZoqRQsTCsikYjQxuq5ywSYikchzHd/4YvFJEtqldTHAZtuFtraLf5EjYDKvNSpAFAgYrZdUHCG1pr0klqCFEW/UvUjRXpgxW3igbJIr5+x9iLCjdF/rtMIu8EiqM7RPWplLMpmrEtbA6gA1mUDjRwpVAaSNuVIAJbkTVxk0b7vRULlZIf4xERREaTXR1s2s5YZHYRIagZkJ1pzIJXPF9hjiyZQ0cHjBxQH+kngsg7BKMVUAR8Z1VdUSijpJAnJwRurnk086AY361zGBYTD1LYR/KqiG6pqwdtLZvpSTJZpDimqkfKqriHbCN5zRKn3bpl22hBAXMqhg1raQIMOUUZ8VQjQiFafiG1Be5aLMrOtIwnuR0DIvm3aFG97zgpAJ85kybfqwJToCL/rY5s4yICLfcwz3ANLRbRIwAwJFYRZBA+VKUNuitLFVxhZqeh1YVJOEkfV36TNC2o+oKbttQGwIszCK2wpBWcnWBYy8TmPBIPFA5B0i1EQpsrrl1xFFHgRQheCcZYA4rjpEJoaXlSXdfoHYkCR5ZTXLB6HlnET6xtkiFIKTLSRJ+KUVQFtm6qz3EoLrDPHjK/lghXHWZd/25ImE15dVqzg1wQzKohSHksrnrC6lJYs/TpokSfeCHIuQmcUhrm1mh8x2IY4n9YSWcP44g9LW60WRWbJxJpaDaHUJW7R1VOXqG9M2kQmqNPXG0bC0TAotycu2Wa8Mqv8xc2T2bDxUkcUxSJu8u5CLlhgQa5OPDbXbIS90Pu/iEXvZtseEheb96KgmHxaRIBuqDWKJJr1RrPFwC9NUr6NELrYzmfwwFoVwsQoMm3qhQK7RqS+r8pqPK/bBOXNgRrKhCAD5JJoF7qieSzQ1hySrFZXpRH3VROtbCycirChgxCel2zfDJkwCUwq/D9SdI5xinMdYORt8Z1qRQ3ofjhwDSVCZnQChfF0h67paPg2lf5q9MkCIfytx9L22Gdmt7WIVosXiO9yYQzQ1VY4EvXWUF52misgM8UHJjleSMTM8vOE1bvePBW0VE7NN7w++fIo/iEKeWdFAXoaWqZCfzWZ0S6+sbiukCua05X4Q+tFJ2QZ12mCO7UemhEP9Lf9ngd7a1oAKkdiJjnabZ6T9M+V0CFH2Drri7nkG4oCWS3ovomnytVKck1G8qfAygkL3S6iSBnJXS2a6E+JJ5kk0ISr14MeF1haZtuS55GNFFFyU0XpRn6J4DPRgSJgMx/dqy+yg9EmcMDCxSACASpBVEmJ24Bi5uahlxZKjE1+ILpMy9CLVFUG/Aitz1Fy0l7PGBumkujpBzvSd1dZWS8Agwtz3krRPjCDmqNMLIndPxgWe3WjGaJ3ZJ9o3EVDWD0VSERnEGdqsQtSylH2eC9LkmKe8L5RWmkhpZkmdCJhtpehWMYCeRhvCWyRnekSq/w1Xpq/SBFJqOANG0gHB3YkRKytQGHZtw9QAMxekS4Z2cdJqDZTGM6W21kpcFGpK1JAvrTA3SRtkWsL2MWXvkEurvqrTsl4Uit2Aa8SdHJKWOX2TFmTUc+FAKE981EQBpTJQAaz/apmqqJk5br/RBpP2TSPzPecyCcD/DzTd/AK3fC+1AAAAAElFTkSuQmCC"

def _build_pdf_reportlab(d, photos, grade, report_id, now, ai_text="", theme="light"):
    """
    REDESIGNED WHITE PDF -- Clean, professional, wave-like flow.
    PAGE 1: Logo header + Hero (photo+grade) + Meta strip + KPI strip + AI Analysis
    PAGE 2: Price banner + Negotiation cards + Full checklist (refined, no dark cols) + Photos
    """
    import re
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
        leftMargin=12*mm, rightMargin=12*mm,
        topMargin=8*mm, bottomMargin=8*mm)
    W = 186*mm

    # ── REFINED WHITE PALETTE ────────────────────────────────
    # Background & Surface
    WHITE     = colors.white
    OFFWHITE  = colors.HexColor("#F8FAFC")   # card / alternating row bg
    SLATE50   = colors.HexColor("#F1F5F9")   # section header bg (very light)
    SLATE100  = colors.HexColor("#E2E8F0")   # borders / dividers
    SLATE200  = colors.HexColor("#CBD5E1")   # strong divider

    # Navy -- primary brand colour (header, accents)
    NAVY      = colors.HexColor("#0B1D3A")   # top bar, footer
    NAVY2     = colors.HexColor("#1E3A6E")   # section headers
    NAVY3     = colors.HexColor("#2D5AA0")   # accent line, section number

    # Text
    TXT       = colors.HexColor("#1E293B")   # body text
    TXT2      = colors.HexColor("#64748B")   # labels / secondary
    TXT3      = colors.HexColor("#94A3B8")   # very muted / placeholders

    # Status colours
    GREEN     = colors.HexColor("#16A34A")   # good
    GREEN_BG  = colors.HexColor("#F0FDF4")   # good card bg
    RED       = colors.HexColor("#DC2626")   # critical / cost
    RED_BG    = colors.HexColor("#FEF2F2")   # bad card bg
    AMBER     = colors.HexColor("#D97706")   # moderate
    AMBER_BG  = colors.HexColor("#FFFBEB")   # amber card bg
    EMERALD   = colors.HexColor("#059669")   # target price, nego lever

    # Section accent stripe colours (left border on section headers)
    ACC1      = colors.HexColor("#2563EB")   # blue
    ACC2      = colors.HexColor("#7C3AED")   # purple (unused -- just palette)

    def s(name, **kw):
        base = dict(fontName="Helvetica", fontSize=9, textColor=TXT,
                    leading=13, spaceAfter=0, spaceBefore=0)
        base.update(kw)
        return ParagraphStyle(name, **base)

    def v(key, default="--"):
        val = str(d.get(key) or default)
        # Handle detail system's "\n-> detail" BEFORE stripping
        val = val.replace("\n-> ", " — ").replace("\\n-> ", " — ")
        # Strip ALL non-ASCII (Cyrillic, emoji, symbols) — \w with re.ASCII only matches [a-zA-Z0-9_]
        val = re.sub(r'[^\x00-\x7F]', '', val)
        # Clean up bilingual " / Russian" artifacts from button labels
        val = re.sub(r'\s*/\s*$', '', val)   # remove trailing " /" or "/ "
        val = re.sub(r'\s+', ' ', val)       # collapse multiple spaces
        return val.strip() or default

    def color_for(val):
        sv = str(val).lower()
        if any(x in sv for x in ["critical","leak","damage","loud","knock","excess","structural",
                                   "active","crack","fail","bad","worn","contaminated","missing",
                                   "flat","warped","replace","low"]):
            return RED
        if any(x in sv for x in ["minor","partial","weak","seep","surface","groov","aging","chips",
                                   "delay","used","pending","stored","not provided","mismatch"]):
            return AMBER
        if any(x in sv for x in ["good","none","normal","correct","smooth","straight","even","working",
                                   "present","full","yes","no rust","no leak","clean","matching","clear",
                                   "responsive","tight","solid","verified","consistent"]):
            return GREEN
        return TXT2

    def _img(b64, w, h):
        if not b64: return None
        try:
            import base64
            img = RLImage(BytesIO(base64.b64decode(b64.split(",",1)[-1])), width=w*mm, height=h*mm)
            img.hAlign = "CENTER"
            return img
        except: return None

    def _composited_logo_b64(logo_b64, w_mm, h_mm, bg_rgb=(11, 29, 58)):
        """Pre-composite RGBA logo onto solid background colour at 4× resolution."""
        try:
            import base64 as _b64
            from PIL import Image as PILImage
            import io
            SCALE = 4
            W_px = int(w_mm * 3.7795 * SCALE)
            H_px = int(h_mm * 3.7795 * SCALE)
            raw = _b64.b64decode(logo_b64.split(",", 1)[-1])
            logo = PILImage.open(io.BytesIO(raw)).convert("RGBA")
            # Scale logo to fit inside target, preserving aspect ratio
            logo.thumbnail((W_px, H_px), PILImage.LANCZOS)
            bg = PILImage.new("RGBA", (W_px, H_px), bg_rgb + (255,))
            # Centre logo on background
            offset = ((W_px - logo.width) // 2, (H_px - logo.height) // 2)
            bg.paste(logo, offset, logo)
            result = bg.convert("RGB")
            buf = io.BytesIO()
            result.save(buf, format="PNG", optimize=True)
            return _b64.b64encode(buf.getvalue()).decode()
        except Exception:
            return logo_b64  # fallback to original if PIL fails

    _logo_composited_b64 = _composited_logo_b64(ARGYN_LOGO_B64, 14, 8)

    # ── TOP HEADER BAR (navy, full width) ───────────────────
    def brand_bar(subtitle="VEHICLE INSPECTION REPORT"):
        logo_img = _img(_logo_composited_b64, 14, 8)
        t = Table([[
            logo_img or Spacer(14*mm, 1),
            Paragraph("ARGYN AUTO",
                      s("bn", fontSize=15, fontName="Helvetica-Bold",
                        textColor=colors.white, leading=18)),
            Paragraph(subtitle,
                      s("bs", fontSize=8, textColor=TXT3, alignment=2, leading=10)),
        ]], colWidths=[18*mm, 110*mm, 58*mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), NAVY),
            ("VALIGN",     (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING", (0,0), (-1,-1), 9),
            ("BOTTOMPADDING",(0,0),(-1,-1),9),
            ("LEFTPADDING", (0,0),(-1,-1), 10),
            ("RIGHTPADDING",(0,0),(-1,-1), 10),
        ]))
        return t

    # ── ACCENT DIVIDER LINE ──────────────────────────────────
    def divider(color=SLATE200, thickness=0.5):
        return HRFlowable(width="100%", thickness=thickness,
                          color=color, spaceAfter=0, spaceBefore=0)

    # ── SECTION HEADER (white bg, left navy accent bar) ──────
    def sec_hdr(title, w=None):
        cw = w or W
        t = Table([[
            Paragraph(title, s("sh", fontSize=7, fontName="Helvetica-Bold",
                               textColor=NAVY2, leading=9)),
        ]], colWidths=[cw])
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,-1), SLATE50),
            ("LINEBEFORE",    (0,0),(0,-1),  3, NAVY3),
            ("LINEBELOW",     (0,0),(-1,-1), 0.5, SLATE200),
            ("TOPPADDING",    (0,0),(-1,-1), 5),
            ("BOTTOMPADDING", (0,0),(-1,-1), 5),
            ("LEFTPADDING",   (0,0),(-1,-1), 10),
            ("RIGHTPADDING",  (0,0),(-1,-1), 8),
        ]))
        return t

    # ── FOOTER ──────────────────────────────────────────────
    def footer(lbl):
        t = Table([[
            Paragraph("ARGYN AUTO",
                      s("fl", fontSize=8, fontName="Helvetica-Bold", textColor=NAVY)),
            Paragraph(f"{report_id}  ·  {now.strftime('%Y-%m-%d')}  ·  {v('location','--')}  ·  {lbl}",
                      s("fr", fontSize=7, textColor=TXT3, alignment=2)),
        ]], colWidths=[60*mm, 126*mm])
        t.setStyle(TableStyle([
            ("LINEABOVE",     (0,0),(-1,-1), 1.5, NAVY),
            ("BACKGROUND",    (0,0),(-1,-1), OFFWHITE),
            ("TOPPADDING",    (0,0),(-1,-1), 5),
            ("BOTTOMPADDING", (0,0),(-1,-1), 5),
            ("LEFTPADDING",   (0,0),(-1,-1), 0),
            ("RIGHTPADDING",  (0,0),(-1,-1), 0),
        ]))
        return t

    # ── CHECKLIST ROW PAIR (label | value) ──────────────────
    def chk(rows, col_w=None):
        cw = col_w or [W/2 * 0.50, W/2 * 0.46]
        data = []
        for label, val in rows:
            vc = color_for(str(val))
            data.append([
                Paragraph(label, s("cl", fontSize=8, textColor=TXT2, leading=11)),
                Paragraph(str(val), s("cv", fontSize=8, textColor=vc,
                                      fontName="Helvetica-Bold", leading=11)),
            ])
        t = Table(data, colWidths=cw)
        t.setStyle(TableStyle([
            ("TOPPADDING",    (0,0),(-1,-1), 3),
            ("BOTTOMPADDING", (0,0),(-1,-1), 3),
            ("LEFTPADDING",   (0,0),(-1,-1), 8),
            ("RIGHTPADDING",  (0,0),(-1,-1), 6),
            ("LINEBELOW",     (0,0),(-1,-2), 0.3, SLATE100),
            ("ROWBACKGROUNDS",(0,0),(-1,-1), [WHITE, OFFWHITE]),
            ("VALIGN",        (0,0),(-1,-1), "TOP"),
        ]))
        return t

    # ── PHOTO ROW (flat 2-row table, no nesting) ─────────────
    def photo_row(keys_labels, h_mm, gap=3):
        n = len(keys_labels)
        pw = (W - gap*mm*(n-1)) / n
        label_row, photo_cells, col_widths = [], [], []
        for i, (key, lbl) in enumerate(keys_labels):
            img = _img(photos.get(key, ""), pw/mm, h_mm)
            content = img if img else Table(
                [[Spacer(1, h_mm*mm)]],
                colWidths=[pw], rowHeights=[h_mm*mm]
            )
            label_row.append(Paragraph(lbl.upper(),
                s(f"phl{i}", fontSize=5, textColor=TXT3, leading=7, alignment=1)))
            photo_cells.append(content)
            col_widths.append(pw)
            if i < n-1:
                label_row.append(Spacer(1,1))
                photo_cells.append(Spacer(1,1))
                col_widths.append(gap*mm)
        t = Table([label_row, photo_cells], colWidths=col_widths,
                  rowHeights=[6*mm, h_mm*mm])
        ts = [
            ("VALIGN",    (0,0),(-1,-1), "MIDDLE"),
            ("ALIGN",     (0,0),(-1,-1), "CENTER"),
            ("TOPPADDING",(0,0),(-1,-1), 0),
            ("BOTTOMPADDING",(0,0),(-1,-1), 0),
            ("LEFTPADDING",(0,0),(-1,-1), 0),
            ("RIGHTPADDING",(0,0),(-1,-1), 0),
        ]
        for i in range(n):
            col = i * 2
            ts.append(("BACKGROUND", (col,1), (col,1), OFFWHITE))
            ts.append(("BOX",        (col,1), (col,1), 0.5, SLATE200))
        t.setStyle(TableStyle(ts))
        return t

    story = []

    # ═══════════════════════════════════════════════════════════════
    # PAGE 1 -- HEADER + HERO + META + KPI + AI ANALYSIS
    # ═══════════════════════════════════════════════════════════════
    story.append(brand_bar("ARGYN AUTO INSPECTION"))

    # ── Hero: front photo (left) + Grade badge (right) ──────
    # Grade colour: always a warm gold/amber regardless of input
    # A=green, B=gold, C=red -- but visually neutral gold is the base
    gl = grade["letter"].upper()
    if gl == "A":
        GRADE_COLOR = colors.HexColor("#16A34A")   # green
        GRADE_BG    = colors.HexColor("#052E16")   # dark green bg
    elif gl == "C":
        GRADE_COLOR = colors.HexColor("#EF4444")   # red
        GRADE_BG    = colors.HexColor("#2D0A0A")   # dark red bg
    else:  # B -- gold/amber, neutral, professional
        GRADE_COLOR = colors.HexColor("#F5A623")   # warm gold
        GRADE_BG    = colors.HexColor("#1A1200")   # very dark amber bg

    # ── HERO: Photo left + Grade panel right ─────────────────
    GRADE_COL_W = 62*mm
    PHOTO_COL_W = W - GRADE_COL_W
    HERO_H      = 104*mm

    # Photo: directly in hero cell (no wrapper table = no extra padding)
    front_img = _img(photos.get("front",""), PHOTO_COL_W/mm, HERO_H/mm)
    photo_content = front_img if front_img else \
        Paragraph("FRONT PHOTO", s("fp", fontSize=12, textColor=TXT3, alignment=1))

    # Grade panel: big letter + 3-card A/B/C legend stacked vertically
    grade_defs = [
        ("A", "Showroom Ready",
         "No major repairs needed. Safe to buy at or near asking price.",
         colors.HexColor("#16A34A"), gl=="A"),
        ("B", "Drive-Worthy",
         "Minor issues present. Negotiate price down before signing.",
         colors.HexColor("#F5A623"), gl=="B"),
        ("C", "High Risk",
         "Serious problems found. Demand major discount or walk away.",
         colors.HexColor("#EF4444"), gl=="C"),
    ]

    # Flat table: letter row + bigrow, stacked for each grade -- no nesting
    # Structure: 3×2 rows (title row + desc row per grade), 2 cols (letter | text)
    CARD_W = GRADE_COL_W  # full width of grade panel
    LTR_W  = 12*mm
    TXT_W  = CARD_W - LTR_W

    legend_rows  = []
    legend_h     = []
    legend_style = []
    ri = 0
    for ltr, title, desc, col, active in grade_defs:
        bg       = colors.HexColor("#0F1D35") if active else colors.HexColor("#0A1525")
        dim_col  = col if active else colors.HexColor("#243852")
        desc_col = colors.HexColor("#8BAAC8") if active else colors.HexColor("#1E2E40")

        legend_rows.append([
            Paragraph(ltr, s(f"ll{ltr}", fontSize=11, fontName="Helvetica-Bold",
                             textColor=col, alignment=1, leading=13)),
            Paragraph(title, s(f"lt{ltr}", fontSize=7, fontName="Helvetica-Bold",
                               textColor=col if active else dim_col, leading=9)),
        ])
        legend_rows.append([
            Paragraph("", s(f"le{ltr}")),
            Paragraph(desc, s(f"ld{ltr}", fontSize=6.5, textColor=desc_col, leading=9)),
        ])
        legend_h += [12*mm, 10*mm]

        # background for both rows of this grade
        legend_style += [
            ("BACKGROUND", (0,ri),(-1,ri+1), bg),
            ("VALIGN",     (0,ri),(-1,ri+1), "MIDDLE"),
            ("TOPPADDING",    (0,ri),(-1,ri),   3),
            ("BOTTOMPADDING", (0,ri),(-1,ri),   1),
            ("TOPPADDING",    (0,ri+1),(-1,ri+1), 1),
            ("BOTTOMPADDING", (0,ri+1),(-1,ri+1), 3),
        ]
        if active:
            legend_style.append(("LINEBEFORE", (0,ri),(0,ri+1), 3, col))
        if ltr != "C":
            legend_style.append(("LINEBELOW", (0,ri+1),(-1,ri+1), 0.3,
                                 colors.HexColor("#1E3A5F")))
        ri += 2

    legend_t = Table(legend_rows, colWidths=[LTR_W, TXT_W], rowHeights=legend_h)
    base = [
        ("BACKGROUND",    (0,0),(-1,-1), colors.HexColor("#0A1525")),
        ("ALIGN",         (0,0),(0,-1),  "CENTER"),
        ("LEFTPADDING",   (0,0),(0,-1),  2),
        ("RIGHTPADDING",  (0,0),(0,-1),  2),
        ("LEFTPADDING",   (1,0),(1,-1),  8),
        ("RIGHTPADDING",  (1,0),(1,-1),  6),
    ]
    legend_t.setStyle(TableStyle(base + legend_style))

    # Big letter + legend stacked -- ALL heights fixed, no overflow possible
    LEGEND_TOTAL = sum(legend_h)
    LETTER_H     = HERO_H - LEGEND_TOTAL

    # Fix legend row heights explicitly (no auto-expand)
    legend_t._argH = [h for h in legend_h]

    grade_panel = Table([
        [Paragraph(gl, s("gl_big", fontSize=52, fontName="Helvetica-Bold",
                         textColor=GRADE_COLOR, alignment=1, leading=56))],
        [legend_t],
    ], colWidths=[GRADE_COL_W], rowHeights=[LETTER_H, LEGEND_TOTAL])
    grade_panel.setStyle(TableStyle([
        ("BACKGROUND", (0,0),(-1,-1), NAVY),
        ("ALIGN",      (0,0),(-1,-1), "CENTER"),
        ("VALIGN",     (0,0),(0,0),   "MIDDLE"),
        ("VALIGN",     (0,1),(0,1),   "TOP"),
        ("PADDING",    (0,0),(-1,-1), 0),
    ]))

    hero = Table([[photo_content, grade_panel]],
                 colWidths=[PHOTO_COL_W, GRADE_COL_W],
                 rowHeights=[HERO_H])
    hero.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(0,0),   SLATE50),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("ALIGN",         (0,0),(0,0),   "CENTER"),
        ("TOPPADDING",    (0,0),(-1,-1), 0),
        ("BOTTOMPADDING", (0,0),(-1,-1), 0),
        ("LEFTPADDING",   (0,0),(-1,-1), 0),
        ("RIGHTPADDING",  (0,0),(-1,-1), 0),
        ("LINEAFTER",     (0,0),(0,-1),  0.5, colors.HexColor("#1E3A5F")),
    ]))
    story.append(hero)

    # ── Meta strip -- 5 columns ──────────────────────────────
    meta_items = [
        ("Make / Model",    v("ymm")),
        ("VIN",             v("vin")),
        ("Odometer",        v("odo")),
        ("Date / Location", f"{v('date')} · {v('location')}"),
        ("Client",          v("client_name")),
    ]
    meta_cells = []
    for lbl, val in meta_items:
        c = Table([
            [Paragraph(lbl, s(f"mk{lbl}", fontSize=7, textColor=TXT2, leading=9))],
            [Paragraph(val, s(f"mv{lbl}", fontSize=9, fontName="Helvetica-Bold",
                              textColor=TXT, leading=12))],
        ], colWidths=[37.2*mm])
        c.setStyle(TableStyle([("PADDING",(0,0),(-1,-1), 6)]))
        meta_cells.append(c)
    meta_t = Table([meta_cells], colWidths=[37.2*mm]*5)
    meta_t.setStyle(TableStyle([
        ("INNERGRID",(0,0),(-1,-1), 0.3, SLATE100),
        ("BOX",      (0,0),(-1,-1), 0.5, SLATE200),
        ("PADDING",  (0,0),(-1,-1), 0),
        ("BACKGROUND",(0,0),(-1,-1), WHITE),
        ("LINEABOVE",(0,0),(-1,0), 3, NAVY3),
    ]))
    story.append(meta_t)

    # ── KPI strip -- 3 numbers ───────────────────────────────
    imm   = v("imm_repair","--")
    fut   = v("future_risk","--")
    nego  = v("nego_range","--")
    ask   = v("asking_price","--")

    # Format imm/fut: prefix $ only if numeric
    def _fmt_money(val):
        try:
            import re as _re
            n = int(float(_re.sub(r'[^\d.]','', val)))
            return f"${n:,}"
        except:
            return val

    imm_fmt = _fmt_money(imm)
    fut_fmt = _fmt_money(fut)

    def kpi_cell(label, val, color, sub="", w=62):
        rows = [
            [Paragraph(label, s(f"kl{label}", fontSize=7, textColor=TXT2, leading=9))],
            [Paragraph(str(val), s(f"kv{label}", fontSize=20, fontName="Helvetica-Bold",
                                   textColor=color, leading=24))],
        ]
        if sub:
            rows.append([Paragraph(sub, s(f"ks{label}", fontSize=7, textColor=TXT3, leading=9))])
        t = Table(rows, colWidths=[w*mm])
        t.setStyle(TableStyle([("PADDING",(0,0),(-1,-1), 8)]))
        return t

    # Format asking price with comma
    try:
        import re as _re2
        ask_num = int(float(_re2.sub(r'[^\d.]', '', ask)))
        ask_fmt = f"${ask_num:,}"
    except:
        ask_fmt = f"${ask}" if ask != "--" else "--"

    kpi_row = [
        kpi_cell("IMMEDIATE REPAIRS", imm_fmt, RED,  f"+{fut_fmt} within 6-12 mo"),
        kpi_cell("NEGOTIATION RANGE",  nego,      GREEN, "Recommended"),
        kpi_cell("ASKING PRICE",       ask_fmt,   TXT,  f"Owners: {v('owners','--')}"),
    ]
    kpi_t = Table([kpi_row], colWidths=[64*mm, 62*mm, 60*mm])
    kpi_t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1), WHITE),
        ("BOX",       (0,0),(-1,-1), 0.5, SLATE200),
        ("INNERGRID", (0,0),(-1,-1), 0.3, SLATE100),
        ("LINEBELOW", (0,0),(-1,-1), 2.5, NAVY),
        ("PADDING",   (0,0),(-1,-1), 0),
    ]))
    story.append(kpi_t)
    story.append(Spacer(1, 2*mm))

    # ── AI Analysis ─────────────────────────────────────────
    ai_hdr = Table([[
        Paragraph("PRE-PURCHASE INSPECTION  ·  AI MARKET ANALYSIS",
                  s("aih", fontSize=9, fontName="Helvetica-Bold",
                    textColor=WHITE, leading=11)),
        Paragraph(f"Powered by Claude  ·  {v('ymm')}  ·  {v('odo')}",
                  s("aim", fontSize=7, textColor=TXT3, alignment=2, leading=9)),
    ]], colWidths=[126*mm, 60*mm])
    ai_hdr.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1), NAVY),
        ("PADDING",   (0,0),(-1,-1), 7),
        ("VALIGN",    (0,0),(-1,-1), "MIDDLE"),
    ]))
    story.append(ai_hdr)

    if ai_text:
        all_k = ["MARKET VALUE","DEPRECIATION","REPAIR COST ESTIMATE",
                 "RISK ASSESSMENT","FINAL VERDICT"]
        parsed = {}
        for key in all_k:
            pat = rf"{key}:\s*(.*?)(?=(?:{'|'.join(all_k)}):|$)"
            m = re.search(pat, ai_text, re.DOTALL|re.IGNORECASE)
            parsed[key] = re.sub(r'#\s*$','',
                                 (m.group(1).strip() if m else "")).strip()

        def clean(t):
            t = re.sub(r'\*\*([^*]+)\*\*', r'\1', t)  # strip **bold**
            t = re.sub(r'\*([^*]+)\*', r'\1', t)       # strip *italic*
            return re.sub(r'[^\x00-\x7F]', '', t).strip()

        # 4-card grid
        defs = [
            ("MARKET VALUE",         "Market Value",    ACC1,  OFFWHITE),
            ("DEPRECIATION",         "Depreciation",    AMBER, AMBER_BG),
            ("REPAIR COST ESTIMATE", "Repair Costs",    RED,   RED_BG),
            ("RISK ASSESSMENT",      "Risk Assessment", TXT2,  OFFWHITE),
        ]
        cw2 = W/2

        def ai_card(key, title, accent, bg):
            body = clean(parsed.get(key,"")) or "--"
            t = Table([
                [Paragraph(title, s(f"ach{key}", fontSize=7, fontName="Helvetica-Bold",
                                    textColor=accent, leading=9))],
                [Paragraph(body,  s(f"acb{key}", fontSize=7.5, textColor=TXT, leading=11))],
            ], colWidths=[cw2])
            t.setStyle(TableStyle([
                ("BACKGROUND",    (0,0),(0,0), colors.HexColor("#FAFBFF") if accent==ACC1 else bg),
                ("BACKGROUND",    (0,1),(0,1), WHITE),
                ("LINEABOVE",     (0,0),(-1,0), 3, accent),
                ("BOX",           (0,0),(-1,-1), 0.5, SLATE100),
                ("TOPPADDING",    (0,0),(0,0), 4),
                ("BOTTOMPADDING", (0,0),(0,0), 4),
                ("TOPPADDING",    (0,1),(0,1), 6),
                ("BOTTOMPADDING", (0,1),(0,1), 6),
                ("LEFTPADDING",   (0,0),(-1,-1), 10),
                ("RIGHTPADDING",  (0,0),(-1,-1), 10),
            ]))
            return t

        cards = [ai_card(k,t,a,b) for k,t,a,b in defs]
        ai_grid = Table([[cards[0], cards[1]], [cards[2], cards[3]]],
                        colWidths=[cw2, cw2])
        ai_grid.setStyle(TableStyle([
            ("VALIGN",        (0,0),(-1,-1), "TOP"),
            ("PADDING",       (0,0),(-1,-1), 0),
            ("RIGHTPADDING",  (0,0),(0,-1),  2),
            ("BOTTOMPADDING", (0,0),(1,0),   3),
        ]))
        story.append(ai_grid)
        story.append(Spacer(1, 2*mm))

        # Final verdict
        verdict = clean(parsed.get("FINAL VERDICT",""))
        if verdict:
            vt = Table([
                [Paragraph("FINAL VERDICT",
                           s("vh", fontSize=7, fontName="Helvetica-Bold",
                             textColor=EMERALD, leading=9))],
                [Paragraph(verdict,
                           s("vb", fontSize=9, fontName="Helvetica-Bold",
                             textColor=TXT, leading=12))],
            ], colWidths=[W])
            vt.setStyle(TableStyle([
                ("BACKGROUND",    (0,0),(0,0), GREEN_BG),
                ("BACKGROUND",    (0,1),(0,1), WHITE),
                ("LINEABOVE",     (0,0),(-1,0), 3.5, EMERALD),
                ("BOX",           (0,0),(-1,-1), 0.5, SLATE100),
                ("TOPPADDING",    (0,0),(0,0), 4),
                ("BOTTOMPADDING", (0,0),(0,0), 4),
                ("TOPPADDING",    (0,1),(0,1), 6),
                ("BOTTOMPADDING", (0,1),(0,1), 6),
                ("LEFTPADDING",   (0,0),(-1,-1), 12),
                ("RIGHTPADDING",  (0,0),(-1,-1), 12),
            ]))
            story.append(vt)
    else:
        no_ai = Table([[Paragraph(
            "Add ANTHROPIC_API_KEY in Railway to enable AI market analysis.",
            s("na", fontSize=9, textColor=TXT2, leading=13))]],
            colWidths=[W])
        no_ai.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,-1), OFFWHITE),
            ("BOX",       (0,0),(-1,-1), 1, SLATE100),
            ("PADDING",   (0,0),(-1,-1), 14),
        ]))
        story.append(no_ai)

    story.append(Spacer(1, 2*mm))
    story.append(CondPageBreak(60*mm))

    # ═══════════════════════════════════════════════════════════════
    # PAGE 2 -- PRICE BANNER + NEGO CARDS + CHECKLIST + PHOTOS
    # ═══════════════════════════════════════════════════════════════
    story.append(brand_bar("ITEMS THAT NEED YOUR ATTENTION  ·  FULL INSPECTION  ·  PHOTOS"))

    # ── Price Banner: Asking → Target ───────────────────────
    asking_raw = v("asking_price","0").replace("$","").replace(",","").strip()
    try:   asking_num = int(float(asking_raw))
    except: asking_num = 0

    nego_str2 = v("nego_range","")
    try:
        nums = re.findall(r'\d[\d,]*', nego_str2.replace("$",""))
        discount = int(nums[0].replace(",","")) if nums else 0
    except: discount = 0

    # If no nego_range, try to extract target price from AI Final Verdict
    if discount == 0 and ai_text:
        # Look for "negotiate to $X" or "offer $X" pattern in AI text
        m = re.search(r'(?:negotiate to|offer|buy at)\s*\$?([\d,]+)', ai_text, re.IGNORECASE)
        if m:
            try:
                ai_target = int(m.group(1).replace(",",""))
                if 0 < ai_target < asking_num:
                    discount = asking_num - ai_target
            except: pass

    target_num = max(0, asking_num - discount)

    if asking_num > 0:
        saved = asking_num - target_num
        price_banner = Table([
            # Row 1: labels
            [Paragraph("ASKING PRICE",
                       s("apl_lbl", fontSize=8, textColor=TXT3, alignment=1, leading=10)),
             Paragraph("",s("xx1")),
             Paragraph("TARGET PRICE",
                       s("tpl_lbl", fontSize=8, textColor=TXT3, alignment=1, leading=10))],
            # Row 2: prices
            [Paragraph(f"${asking_num:,}",
                       s("apl_val", fontSize=26, fontName="Helvetica-Bold",
                         textColor=RED, alignment=1, leading=30)),
             Paragraph("→",
                       s("arr", fontSize=20, fontName="Helvetica-Bold",
                         textColor=colors.HexColor("#4A6FA5"), alignment=1, leading=24)),
             Paragraph(f"${target_num:,}",
                       s("tpl_val", fontSize=26, fontName="Helvetica-Bold",
                         textColor=EMERALD, alignment=1, leading=30))],
            # Row 3: YOU SAVE
            [Paragraph("", s("xx2")),
             Spacer(1,1),
             Paragraph(f"YOU SAVE  ${saved:,}",
                       s("ys", fontSize=11, fontName="Helvetica-Bold",
                         textColor=EMERALD, alignment=1, leading=14))],
        ], colWidths=[82*mm, 22*mm, 82*mm])
        price_banner.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,-1), NAVY),
            ("TOPPADDING",    (0,0),(-1,-1), 10),
            ("BOTTOMPADDING", (0,0),(-1,-1), 10),
            ("LEFTPADDING",   (0,0),(-1,-1), 12),
            ("RIGHTPADDING",  (0,0),(-1,-1), 12),
            ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
            ("ALIGN",         (0,0),(-1,-1), "CENTER"),
            ("LINEAFTER",     (0,0),(0,-1),  0.5, colors.HexColor("#1E3A5F")),
            ("LINEAFTER",     (1,0),(1,-1),  0.5, colors.HexColor("#1E3A5F")),
        ]))
        story.append(price_banner)

    story.append(Spacer(1, 4*mm))

    # ── Negotiation section header ───────────────────────────
    nego_hdr = Table([[
        Paragraph("ITEMS THAT NEED YOUR ATTENTION",
                  s("nh", fontSize=9, fontName="Helvetica-Bold",
                    textColor=WHITE, leading=11)),
        Paragraph(f"Total repairs: {imm_fmt} immediate  +  {fut_fmt} future",
                  s("nh2", fontSize=7, textColor=TXT3, alignment=2, leading=9)),
    ]], colWidths=[100*mm, 86*mm])
    nego_hdr.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1), NAVY),
        ("PADDING",   (0,0),(-1,-1), 8),
        ("VALIGN",    (0,0),(-1,-1), "MIDDLE"),
    ]))
    story.append(nego_hdr)
    story.append(Spacer(1, 2*mm))

    # ── Nego cards (flat, white bg, refined) ─────────────────
    nego_items = [
        (v("nego1",""), v("cost1","")),
        (v("nego2",""), v("cost2","")),
        (v("nego3",""), v("cost3","")),
    ]
    total_cost = 0
    accents = [AMBER, ACC1, TXT2]
    acc_bgs  = [AMBER_BG, colors.HexColor("#EFF6FF"), OFFWHITE]

    for i, (issue, cost) in enumerate(nego_items):
        if not issue or issue == "--": continue
        try:
            cn = int(float(re.sub(r'[^\d.]','', cost)))
            total_cost += cn
            cost_str = f"${cn:,}"
        except:
            cn = 0; cost_str = cost if cost not in ("--","") else "--"

        acc = accents[i % 3]
        acc_bg = acc_bgs[i % 3]

        badge_w = 16*mm
        cost_w  = 52*mm
        body_w  = W - badge_w - cost_w - 2*mm

        card = Table([[
            Paragraph(f"#{i+1}",
                      s(f"nb{i}", fontSize=16, fontName="Helvetica-Bold",
                        textColor=acc, alignment=1, leading=20)),
            Paragraph(issue,
                      s(f"ni{i}", fontSize=10, fontName="Helvetica-Bold",
                        textColor=TXT, leading=13)),
            Paragraph(cost_str,
                      s(f"nc{i}", fontSize=20, fontName="Helvetica-Bold",
                        textColor=RED, alignment=2, leading=24)),
        ]], colWidths=[badge_w, body_w, cost_w])
        card.setStyle(TableStyle([
            ("BOX",           (0,0),(-1,-1), 0.5, SLATE100),
            ("LINEBEFORE",    (0,0),(0,-1),  3.5, acc),
            ("BACKGROUND",    (0,0),(0,-1),  acc_bg),
            ("BACKGROUND",    (1,0),(1,-1),  WHITE),
            ("BACKGROUND",    (2,0),(2,-1),  WHITE),
            ("LINEBELOW",     (0,0),(-1,-1), 0.3, SLATE100),
            ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
            ("TOPPADDING",    (0,0),(-1,-1), 10),
            ("BOTTOMPADDING", (0,0),(-1,-1), 10),
            ("LEFTPADDING",   (0,0),(0,-1),  8),
            ("LEFTPADDING",   (1,0),(1,-1),  10),
            ("RIGHTPADDING",  (2,0),(2,-1),  12),
        ]))
        story.append(card)

    story.append(Spacer(1, 2*mm))

    # ── Total + Discount bar (navy, white text) ──────────────
    nego_args = v("nego_args","")
    total_bar = Table([
        [Paragraph("TOTAL REPAIR ESTIMATE",
                   s("trl", fontSize=7, textColor=TXT3, alignment=1, leading=9)),
         Paragraph("RECOMMENDED DISCOUNT",
                   s("rrl", fontSize=7, textColor=TXT3, alignment=1, leading=9))],
        [Paragraph(f"${total_cost:,}",
                   s("trv", fontSize=22, fontName="Helvetica-Bold",
                     textColor=RED, alignment=1, leading=26)),
         Paragraph(nego_str2 or "--",
                   s("rrv", fontSize=22, fontName="Helvetica-Bold",
                     textColor=EMERALD, alignment=1, leading=26))],
        [Paragraph("", s("x")),
         Paragraph(nego_args,
                   s("rrs", fontSize=8, textColor=TXT3, alignment=1, leading=10))
                   if nego_args else Paragraph("", s("x2"))],
    ], colWidths=[93*mm, 93*mm])
    total_bar.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), NAVY),
        ("TOPPADDING",    (0,0),(-1,-1), 12),
        ("BOTTOMPADDING", (0,0),(-1,-1), 12),
        ("LEFTPADDING",   (0,0),(-1,-1), 8),
        ("RIGHTPADDING",  (0,0),(-1,-1), 8),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("ALIGN",         (0,0),(-1,-1), "CENTER"),
        ("LINEAFTER",     (0,0),(0,-1),  0.5, colors.HexColor("#1E3A5F")),
    ]))
    story.append(total_bar)
    story.append(Spacer(1, 5*mm))

    # ── Full Inspection Checklist ────────────────────────────
    # Header
    chk_hdr = Table([[Paragraph("FULL INSPECTION CHECKLIST",
                                s("ch", fontSize=9, fontName="Helvetica-Bold",
                                  textColor=WHITE, leading=11))]],
                    colWidths=[W])
    chk_hdr.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1), NAVY),
        ("PADDING",   (0,0),(-1,-1), 7),
    ]))
    story.append(chk_hdr)
    story.append(Spacer(1, 2*mm))

    # Two-column checklist layout
    # Column widths for chk() inner tables
    half = W/2 - 2*mm
    cw_inner = [half * 0.52, half * 0.44]

    # LEFT column sections
    left_sections = [
        ("ENGINE & OBD", [
            ("Oil level",          v("oil")),
            ("Oil leaks",          v("oil_leak")),
            ("Coolant leaks",      v("coolant_leak")),
            ("Engine noise",       v("engine_noise")),
            ("Exhaust / Cold start", f"{v('exhaust')} / {v('cold_start')}"),
            ("OBD active codes",   v("obd_active")),
            ("Pending / Cleared",  f"{v('obd_pending')} / {v('obd_cleared')}"),
        ]),
        ("BRAKES & BATTERY", [
            ("Front pads",         v("brake_front")),
            ("Rear pads",          v("brake_rear")),
            ("Rotors",             v("brake_rotor")),
            ("Brake vibration",    v("brake_vib")),
            ("Battery voltage",    v("batt_volt")),
            ("Battery age",        v("batt_age")),
            ("Terminals",          v("batt_term")),
        ]),
        ("TRANSMISSION", [
            ("Shift quality",      v("trans_shift")),
            ("Trans leaks",        v("trans_leak")),
        ]),
        ("TOP CONCERNS", None),  # special
    ]

    # RIGHT column sections
    right_sections = [
        ("BODY & STRUCTURE", [
            ("Frame",              v("frame")),
            ("Undercarriage rust", v("rust")),
            ("Panel gaps",         v("panel_gaps")),
            ("Repaint signs",      v("repaint")),
            ("Windshield",         v("windshield")),
            ("Doors",              v("doors")),
        ]),
        ("SUSPENSION & STEERING", [
            ("Suspension noise",   v("susp_noise")),
            ("Control arms",       v("control_arms")),
            ("Shocks",             v("shocks")),
            ("Steering",           v("steering")),
            ("Wheel bearing",      v("wheel_bearing")),
        ]),
        ("TIRES", [
            ("Front tread",        v("tire_front")),
            ("Rear tread",         v("tire_rear")),
            ("Uneven wear",        v("tire_wear")),
            ("DOT year",           v("tire_dot")),
            ("Dry rot",            v("tire_rot")),
            ("Brand match / Spare", f"{v('tire_match')} / {v('spare')}"),
        ]),
        ("ROAD TEST & INTERIOR", [
            ("Engine / Trans",     f"{v('rt_engine')} / {v('rt_trans')}"),
            ("Brakes / Alignment", f"{v('rt_brakes')} / {v('rt_align')}"),
            ("Suspension (drive)", v("rt_susp")),
            ("Warning lights",     v("rt_lights")),
            ("AC / Windows",       f"{v('int_ac')} / {v('int_win')}"),
            ("Seatbelts / Damage", f"{v('int_belts')} / {v('int_damage')}"),
        ]),
    ]

    # Build left elements
    left_els = []
    for title, rows in left_sections:
        if rows is None:  # TOP CONCERNS special block
            left_els.append(sec_hdr("TOP CONCERNS", w=half))
            concerns_txt = " / ".join(filter(None,[
                d.get("nego1",""), d.get("nego2",""), d.get("nego3","")])) or "No major concerns"
            concerns_txt = re.sub(r'[^\x00-\x7F]','', concerns_txt).strip()
            tc = Table([[Paragraph(concerns_txt,
                                   s("tc", fontSize=8, textColor=AMBER,
                                     fontName="Helvetica-Bold", leading=12))]],
                       colWidths=[half])
            tc.setStyle(TableStyle([
                ("PADDING",    (0,0),(-1,-1), 6),
                ("LINEBEFORE", (0,0),(0,-1),  3, AMBER),
                ("BACKGROUND", (0,0),(-1,-1), AMBER_BG),
                ("BOX",        (0,0),(-1,-1), 0.3, SLATE100),
            ]))
            left_els.append(tc)
            # Inspector comment
            left_els.append(sec_hdr("INSPECTOR COMMENT", w=half))
            comment_raw = re.sub(r'[^\x00-\x7F]','', v("final_comment","--")).strip()
            tcomm = Table([[Paragraph(comment_raw,
                                      s("ic", fontSize=8, textColor=ACC1, leading=13))]],
                          colWidths=[half])
            tcomm.setStyle(TableStyle([
                ("PADDING",    (0,0),(-1,-1), 7),
                ("LINEBEFORE", (0,0),(0,-1),  3, ACC1),
                ("BACKGROUND", (0,0),(-1,-1), colors.HexColor("#EFF6FF")),
                ("BOX",        (0,0),(-1,-1), 0.3, SLATE100),
            ]))
            left_els.append(tcomm)
        else:
            left_els.append(sec_hdr(title, w=half))
            left_els.append(chk(rows, cw_inner))

    # Build right elements
    right_els = []
    for title, rows in right_sections:
        right_els.append(sec_hdr(title, w=half))
        right_els.append(chk(rows, cw_inner))

    # Pad to equal length
    while len(left_els) < len(right_els):  left_els.append(Spacer(1, 1))
    while len(right_els) < len(left_els):  right_els.append(Spacer(1, 1))

    two_col = Table([[l, r] for l, r in zip(left_els, right_els)],
                    colWidths=[half, half])
    two_col.setStyle(TableStyle([
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
        ("PADDING",       (0,0),(-1,-1), 0),
        ("TOPPADDING",    (0,0),(-1,-1), 1),
        ("RIGHTPADDING",  (0,0),(0,-1),  3),
        ("LEFTPADDING",   (1,0),(1,-1),  3),
    ]))
    story.append(two_col)
    story.append(Spacer(1, 4*mm))

    # ── Inspection Photos ────────────────────────────────────
    ph_hdr = Table([[Paragraph("INSPECTION PHOTOS",
                               s("ph", fontSize=9, fontName="Helvetica-Bold",
                                 textColor=WHITE, leading=11))]],
                   colWidths=[W])
    ph_hdr.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1), NAVY),
        ("PADDING",   (0,0),(-1,-1), 7),
    ]))
    story.append(ph_hdr)
    story.append(Spacer(1, 3*mm))
    story.append(photo_row(
        [("front","Front Exterior"),("rear","Rear Exterior"),
         ("left","Driver Side"),("right","Passenger Side")], 48))
    story.append(Spacer(1, 2*mm))
    story.append(photo_row(
        [("engine","Engine Bay"),("under","Undercarriage"),
         ("interior","Interior"),("odo","Odometer")], 30))
    story.append(Spacer(1, 3*mm))
    story.append(footer("Page 2 of 2"))

    doc.build(story)
    buf.seek(0)
    return buf.read()


async def test_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Generate a sample PDF with dummy data for testing."""
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ Access denied.")
        return
    await update.message.reply_text("⏳ Generating test PDF...")
    d = {
        "client_name": "Test Client",
        "asking_price": "28500",
        "owners": "2",
        "service_hist": "Full service history available",
        "vin": "TEST1234567890",
        "ymm": "2019 BMW 435i",
        "odo": "87,000 km",
        "trans": "Automatic",
        "keys": "2",
        "date": "2026-03-09",
        "location": "Toronto, ON",
        "frame": "Straight, no damage",
        "panel_gaps": "Even and consistent",
        "repaint": "None detected",
        "windshield": "Clear, no chips",
        "doors": "All functioning normally",
        "tire_front": "7mm",
        "tire_rear": "6mm",
        "tire_wear": "Even",
        "tire_dot": "2022",
        "tire_rot": "None",
        "tire_match": "Yes, matching",
        "spare": "Present",
        "oil": "Clean, full",
        "oil_leak": "None",
        "coolant_leak": "None",
        "engine_noise": "Quiet, normal",
        "exhaust": "No smoke",
        "cold_start": "Smooth",
        "rust": "Minor surface rust only",
        "brake_front": "6mm",
        "brake_rear": "5mm",
        "brake_rotor": "Good condition",
        "brake_vib": "None",
        "susp_noise": "None",
        "control_arms": "Tight, no play",
        "shocks": "Firm, no leaks",
        "steering": "Responsive, no play",
        "wheel_bearing": "Quiet",
        "int_dash": "Clean, no warning lights",
        "int_ac": "Works cold",
        "int_win": "All working",
        "int_belts": "Present and functional",
        "int_damage": "None",
        "batt_volt": "12.6V",
        "batt_age": "2 years",
        "batt_term": "Clean",
        "obd_active": "0 codes",
        "obd_pending": "0 codes",
        "obd_cleared": "No recent clearing",
        "trans_shift": "Smooth",
        "trans_leak": "None",
        "rt_engine": "Smooth power delivery",
        "rt_trans": "Shifts correctly",
        "rt_brakes": "Responsive, straight stop",
        "rt_align": "Straight",
        "rt_susp": "Firm and comfortable",
        "rt_lights": "All working",
        "nego1": "Tires need replacement soon",
        "cost1": "800",
        "nego2": "Minor service due",
        "cost2": "400",
        "nego3": "",
        "cost3": "",
        "nego_args": "Tires at minimum, service overdue",
        "nego_range": "1000-2000",
        "overall": "good",
        "recommend": "Yes -- recommend purchase",
        "final_comment": "Well-maintained vehicle, good history. Minor items to address.",
        "imm_repair": "800",
        "future_risk": "400",
    }
    try:
        grade = {"letter": "A", "label": "Good Condition", "color": "#22C55E"}
        from datetime import datetime
        now = datetime.now()
        report_id = f"AA-TEST-{now.strftime('%Y%m%d%H%M')}"
        ai_text = await _get_ai_analysis(d)
        pdf_bytes = _build_pdf_reportlab(d, {}, grade, report_id, now, ai_text=ai_text, theme="light")
        from io import BytesIO
        pdf_bio = BytesIO(pdf_bytes)
        pdf_bio.name = "ARGYN_AUTO_TEST.pdf"
        # Save to Supabase
        saved = await _save_to_supabase(report_id, d, {}, grade, ai_text)
        report_url = f"{SITE_URL}/report/{report_id}" if saved else None
        caption = "✅ Test PDF generated successfully!"
        if report_url:
            caption += f"\n\n🌐 Report link:\n{report_url}"
        else:
            caption += "\n\n⚠️ Supabase save failed — check logs"
        await update.message.reply_document(
            document=pdf_bio,
            filename="ARGYN_AUTO_TEST.pdf",
            caption=caption
        )
    except Exception as e:
        import traceback
        await update.message.reply_text(f"❌ Error: {str(e)[:500]}\n\n{traceback.format_exc()[:500]}")


# ─── CANCEL ───────────────────────────────────────────────

async def dbtest_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Test Supabase connection."""
    if update.effective_user.id not in ALLOWED_USERS:
        return
    import json, httpx
    if not SUPABASE_URL or not SUPABASE_KEY:
        await update.message.reply_text("❌ SUPABASE_URL or SUPABASE_KEY not set in Railway Variables")
        return
    try:
        test_payload = {"id": "TEST-CONN-001", "vin": "test", "ymm": "test", "client_name": "test",
                        "location": "test", "inspection_date": "2026-01-01", "grade": "A",
                        "ai_text": "", "data": {}, "photos": {}}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{SUPABASE_URL}/rest/v1/reports",
                headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                         "Content-Type": "application/json", "Prefer": "return=minimal"},
                content=json.dumps(test_payload)
            )
        if resp.status_code in (200, 201):
            await update.message.reply_text("✅ Supabase connection OK! Report link will work.")
        else:
            await update.message.reply_text(f"❌ Supabase error {resp.status_code}:\n{resp.text[:300]}")
    except Exception as e:
        await update.message.reply_text(f"❌ Exception: {str(e)[:300]}")


async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    lang = ctx.user_data.get("lang", "en")
    await update.message.reply_text(
        T[lang]["cancelled"],
        reply_markup=ReplyKeyboardRemove()
    )
    ctx.user_data.clear()
    return ConversationHandler.END


# ─── MAIN ─────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANG:           [MessageHandler(filters.TEXT & ~filters.COMMAND, set_lang)],
            PDF_THEME:      [MessageHandler(filters.TEXT & ~filters.COMMAND, get_pdf_theme)],
            CLIENT_NAME:    [MessageHandler(filters.TEXT & ~filters.COMMAND, get_client_name)],
            ASKING_PRICE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, get_asking_price)],
            OWNERS:         [MessageHandler(filters.TEXT & ~filters.COMMAND, get_owners)],
            SERVICE_HIST:   [MessageHandler(filters.TEXT & ~filters.COMMAND, get_service_hist)],
            VIN:            [MessageHandler(filters.TEXT & ~filters.COMMAND, get_vin)],
            PHOTO_VIN:      [MessageHandler(filters.PHOTO | filters.TEXT, get_photo_vin)],
            YMM:            [MessageHandler(filters.TEXT & ~filters.COMMAND, get_ymm)],
            ODO:            [MessageHandler(filters.TEXT & ~filters.COMMAND, get_odo)],
            PHOTO_ODO:      [MessageHandler(filters.PHOTO | filters.TEXT, get_photo_odo)],
            TRANS:          [MessageHandler(filters.TEXT & ~filters.COMMAND, get_trans)],
            KEYS:           [MessageHandler(filters.TEXT & ~filters.COMMAND, get_keys)],
            DATE:           [MessageHandler(filters.TEXT & ~filters.COMMAND, get_date)],
            LOCATION:       [MessageHandler(filters.TEXT & ~filters.COMMAND, get_location)],
            DETAIL:         [MessageHandler(filters.TEXT & ~filters.COMMAND, get_detail)],
            PHOTO_FRONT:    [MessageHandler(filters.PHOTO | filters.TEXT, get_photo_front)],
            PHOTO_REAR:     [MessageHandler(filters.PHOTO | filters.TEXT, get_photo_rear)],
            PHOTO_LEFT:     [MessageHandler(filters.PHOTO | filters.TEXT, get_photo_left)],
            PHOTO_RIGHT:    [MessageHandler(filters.PHOTO | filters.TEXT, get_photo_right)],
            FRAME:          [MessageHandler(filters.TEXT & ~filters.COMMAND, get_frame)],
            PANEL_GAPS:     [MessageHandler(filters.TEXT & ~filters.COMMAND, get_panel_gaps)],
            REPAINT:        [MessageHandler(filters.TEXT & ~filters.COMMAND, get_repaint)],
            WINDSHIELD:     [MessageHandler(filters.TEXT & ~filters.COMMAND, get_windshield)],
            DOORS:          [MessageHandler(filters.TEXT & ~filters.COMMAND, get_doors)],
            TIRE_FRONT:     [MessageHandler(filters.TEXT & ~filters.COMMAND, get_tire_front)],
            TIRE_REAR:      [MessageHandler(filters.TEXT & ~filters.COMMAND, get_tire_rear)],
            TIRE_WEAR:      [MessageHandler(filters.TEXT & ~filters.COMMAND, get_tire_wear)],
            TIRE_DOT:       [MessageHandler(filters.TEXT & ~filters.COMMAND, get_tire_dot)],
            TIRE_ROT:       [MessageHandler(filters.TEXT & ~filters.COMMAND, get_tire_rot)],
            TIRE_MATCH:     [MessageHandler(filters.TEXT & ~filters.COMMAND, get_tire_match)],
            SPARE:          [MessageHandler(filters.TEXT & ~filters.COMMAND, get_spare)],
            PHOTO_ENGINE:   [MessageHandler(filters.PHOTO | filters.TEXT, get_photo_engine)],
            OIL:            [MessageHandler(filters.TEXT & ~filters.COMMAND, get_oil)],
            OIL_LEAK:       [MessageHandler(filters.TEXT & ~filters.COMMAND, get_oil_leak)],
            COOLANT_LEAK:   [MessageHandler(filters.TEXT & ~filters.COMMAND, get_coolant_leak)],
            ENGINE_NOISE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, get_engine_noise)],
            EXHAUST:        [MessageHandler(filters.TEXT & ~filters.COMMAND, get_exhaust)],
            COLD_START:     [MessageHandler(filters.TEXT & ~filters.COMMAND, get_cold_start)],
            PHOTO_UNDER:    [MessageHandler(filters.PHOTO | filters.TEXT, get_photo_under)],
            RUST:           [MessageHandler(filters.TEXT & ~filters.COMMAND, get_rust)],
            BRAKE_FRONT:    [MessageHandler(filters.TEXT & ~filters.COMMAND, get_brake_front)],
            BRAKE_REAR:     [MessageHandler(filters.TEXT & ~filters.COMMAND, get_brake_rear)],
            BRAKE_ROTOR:    [MessageHandler(filters.TEXT & ~filters.COMMAND, get_brake_rotor)],
            SUSP_NOISE:     [MessageHandler(filters.TEXT & ~filters.COMMAND, get_susp_noise)],
            CONTROL_ARMS:   [MessageHandler(filters.TEXT & ~filters.COMMAND, get_control_arms)],
            SHOCKS:         [MessageHandler(filters.TEXT & ~filters.COMMAND, get_shocks)],
            STEERING:       [MessageHandler(filters.TEXT & ~filters.COMMAND, get_steering)],
            WHEEL_BEARING:  [MessageHandler(filters.TEXT & ~filters.COMMAND, get_wheel_bearing)],
            PHOTO_INTERIOR: [MessageHandler(filters.PHOTO | filters.TEXT, get_photo_interior)],
            INT_DASH:       [MessageHandler(filters.TEXT & ~filters.COMMAND, get_int_dash)],
            INT_AC:         [MessageHandler(filters.TEXT & ~filters.COMMAND, get_int_ac)],
            INT_WIN:        [MessageHandler(filters.TEXT & ~filters.COMMAND, get_int_win)],
            INT_BELTS:      [MessageHandler(filters.TEXT & ~filters.COMMAND, get_int_belts)],
            INT_DAMAGE:     [MessageHandler(filters.TEXT & ~filters.COMMAND, get_int_damage)],
            BATT_VOLT:      [MessageHandler(filters.TEXT & ~filters.COMMAND, get_batt_volt)],
            BATT_AGE:       [MessageHandler(filters.TEXT & ~filters.COMMAND, get_batt_age)],
            BATT_TERM:      [MessageHandler(filters.TEXT & ~filters.COMMAND, get_batt_term)],
            OBD_ACTIVE:     [MessageHandler(filters.TEXT & ~filters.COMMAND, get_obd_active)],
            OBD_PENDING:    [MessageHandler(filters.TEXT & ~filters.COMMAND, get_obd_pending)],
            OBD_CLEARED:    [MessageHandler(filters.TEXT & ~filters.COMMAND, get_obd_cleared)],
            TRANS_SHIFT:    [MessageHandler(filters.TEXT & ~filters.COMMAND, get_trans_shift)],
            TRANS_LEAK:     [MessageHandler(filters.TEXT & ~filters.COMMAND, get_trans_leak)],
            RT_ENGINE:      [MessageHandler(filters.TEXT & ~filters.COMMAND, get_rt_engine)],
            RT_TRANS:       [MessageHandler(filters.TEXT & ~filters.COMMAND, get_rt_trans)],
            RT_BRAKES:      [MessageHandler(filters.TEXT & ~filters.COMMAND, get_rt_brakes)],
            BRAKE_VIB:      [MessageHandler(filters.TEXT & ~filters.COMMAND, get_brake_vib)],
            RT_ALIGN:       [MessageHandler(filters.TEXT & ~filters.COMMAND, get_rt_align)],
            RT_SUSP:        [MessageHandler(filters.TEXT & ~filters.COMMAND, get_rt_susp)],
            RT_LIGHTS:      [MessageHandler(filters.TEXT & ~filters.COMMAND, get_rt_lights)],
            NEGO1:          [MessageHandler(filters.TEXT & ~filters.COMMAND, get_nego1)],
            NEGO2:          [MessageHandler(filters.TEXT, get_nego2)],
            NEGO3:          [MessageHandler(filters.TEXT, get_nego3)],
            OVERALL:        [MessageHandler(filters.TEXT & ~filters.COMMAND, get_overall)],
            RECOMMEND:      [MessageHandler(filters.TEXT & ~filters.COMMAND, get_recommend)],
            FINAL_COMMENT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, get_final_comment)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("test", test_cmd))
    app.add_handler(CommandHandler("dbtest", dbtest_cmd))
    print("Bot is running...")
    import time
    time.sleep(3)  # wait for old instance to die
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
