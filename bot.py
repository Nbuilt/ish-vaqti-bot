import os, json, re
from datetime import datetime
import pytz
import gspread
from google.oauth2.service_account import Credentials
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TZ = pytz.timezone("Asia/Tashkent")

BOT_TOKEN = os.getenv("BOT_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")

ws = None  # RAW_DATA worksheet

def normalize_phone(p: str) -> str:
    if not p:
        return ""
    digits = re.sub(r"\\D", "", p)
    if not digits:
        return ""
    if digits.startswith("998"):
        return "+" + digits
    if digits.startswith("8") and len(digits) > 10:
        return "+" + digits[1:]
    return "+" + digits

def now():
    dt = datetime.now(TZ)
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S")

def main_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["🟢 Ish boshlandi", "🔴 Ish tugadi"],
            [KeyboardButton("📍 Lokatsiya yuborish", request_location=True)]
        ],
        resize_keyboard=True
    )

def phone_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📞 Telefon raqamni yuborish", request_contact=True)]],
        resize_keyboard=True
    )

def get_ws():
    if not (GOOGLE_CREDS_JSON and SHEET_ID):
        raise RuntimeError("Missing GOOGLE_CREDS_JSON or SHEET_ID env vars")
    creds = Credentials.from_service_account_info(
        json.loads(GOOGLE_CREDS_JSON),
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    gc = gspread.authorize(creds)
    return gc.open_by_key(SHEET_ID).worksheet("RAW_DATA")

def get_sheet(name: str):
    return ws.spreadsheet.worksheet(name)

def allowed_phones_set():
    access = get_sheet("ACCESS_LIST").col_values(1)
    return set(normalize_phone(x) for x in access if str(x).strip())

def has_started_today(phone: str, sana: str) -> bool:
    rows = ws.get_all_values()
    for r in rows[1:]:
        if len(r) > 4 and normalize_phone(r[1]) == phone and r[4] == sana:
            return True
    return False

def find_last_open_row(phone: str, sana: str):
    rows = ws.get_all_values()
    for i in range(len(rows), 1, -1):
        r = rows[i-1]
        if len(r) < 7:
            continue
        if normalize_phone(r[1]) == phone and r[4] == sana and str(r[6]).strip() == "":
            return i
    return None

def get_today_stats(phone: str, sana: str):
    calc = get_sheet("CALC")
    rows = calc.get_all_values()

    hours = 0.0
    ball = 0.0
    for r in rows[1:]:
        # CALC: A Telefon, B Sana, E Ish_soati, G Jami_ball
        if len(r) > 6 and normalize_phone(r[0]) == phone and r[1] == sana:
            try:
                hours += float(r[4])
            except:
                pass
            try:
                ball += float(r[6])
            except:
                pass

    h = int(hours)
    m = int((hours - h) * 60)
    return h, m, int(ball)

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ws
    if ws is None:
        ws = get_ws()

    if context.user_data.get("authorized"):
        await update.message.reply_text("Bot tayyor ✅", reply_markup=main_keyboard())
    else:
        await update.message.reply_text(
            "Botdan foydalanish uchun telefon raqamingizni yuboring.",
            reply_markup=phone_keyboard()
        )

async def on_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ws
    if ws is None:
        ws = get_ws()

    phone = normalize_phone(update.message.contact.phone_number)
    allowed = allowed_phones_set()

    if phone not in allowed:
        await update.message.reply_text(
            f"❌ Sizga botdan foydalanish ruxsati yo‘q.\\n"
            f"Siz yuborgan telefon: {phone}\\n\\n"
            f"✅ ACCESS_LIST listiga shu formatda qo‘shing: {phone}"
        )
        return

    context.user_data["authorized"] = True
    context.user_data["phone"] = phone

    await update.message.reply_text(
        "✅ Telefon tasdiqlandi. Endi botdan foydalanishingiz mumkin.",
        reply_markup=main_keyboard()
    )

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ws
    if ws is None:
        ws = get_ws()

    if not context.user_data.get("authorized"):
        await update.message.reply_text(
            "📞 Avval telefon raqamingizni yuboring.",
            reply_markup=phone_keyboard()
        )
        return

    txt = (update.message.text or "").strip()
    phone = context.user_data["phone"]
    sana, vaqt = now()

    if txt in ["🟢 Ish boshlandi", "🟢 Start"]:
        if has_started_today(phone, sana):
            await update.message.reply_text(
                "❌ Bugun Ish boshlandi allaqachon bosilgan.",
                reply_markup=main_keyboard()
            )
            return
        context.user_data["pending"] = "start"
        await update.message.reply_text("📍 Lokatsiya yuboring.", reply_markup=main_keyboard())
        return

    if txt in ["🔴 Ish tugadi", "🔴 End"]:
        row = context.user_data.get("open_row")
        row_date = context.user_data.get("open_date")

        if (not row) or (row_date != sana):
            row = find_last_open_row(phone, sana)

        if not row:
            await update.message.reply_text("❗ Avval 🟢 Ish boshlandi bosing.")
            return

        ws.update_acell(f"G{row}", vaqt)

        context.user_data.pop("open_row", None)
        context.user_data.pop("open_date", None)

        h, m, ball = get_today_stats(phone, sana)
        warn = "\\n⚠️ Diqqat! Ball minusda." if ball < 0 else ""

        await update.message.reply_text(
            f"✅ Ish tugadi!\\n\\n"
            f"⏱ Bugun ishlagan vaqtingiz: {h} soat {m} minut\\n"
            f"⭐ Bugun jami ballingiz: {ball}{warn}\\n\\n"
            "📊 Ma’lumotlar Sheets’ga yozildi.",
            reply_markup=main_keyboard()
        )
        return

    await update.message.reply_text("Tugmalardan foydalaning 👇", reply_markup=main_keyboard())

async def on_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ws
    if ws is None:
        ws = get_ws()

    if not context.user_data.get("authorized"):
        await update.message.reply_text(
            "📞 Avval telefon raqamingizni yuboring.",
            reply_markup=phone_keyboard()
        )
        return

    if context.user_data.get("pending") != "start":
        return

    phone = context.user_data["phone"]
    user = update.effective_user
    sana, vaqt = now()

    ws.append_row([
        str(user.id),          # TelegramID
        phone,                 # Telefon
        user.last_name or "",  # Familya
        user.first_name or "", # Ism
        sana,                  # Sana
        vaqt,                  # Boshladi
        "",                    # Tugadi
        "bor"                  # Lokatsiya
    ])

    row_index = len(ws.get_all_values())
    context.user_data["open_row"] = row_index
    context.user_data["open_date"] = sana

    context.user_data.pop("pending", None)

    await update.message.reply_text("✅ Ish boshlandi yozildi.", reply_markup=main_keyboard())

async def monthly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ws
    if ws is None:
        ws = get_ws()

    if not context.user_data.get("authorized"):
        await update.message.reply_text("📞 Avval telefonni tasdiqlang.", reply_markup=phone_keyboard())
        return

    phone = context.user_data["phone"]
    month = datetime.now(TZ).strftime("%Y-%m")
    calc = get_sheet("CALC")

    total_h = 0.0
    total_b = 0.0

    for r in calc.get_all_values()[1:]:
        if len(r) > 6 and normalize_phone(r[0]) == phone and r[1].startswith(month):
            try:
                total_h += float(r[4])
            except:
                pass
            try:
                total_b += float(r[6])
            except:
                pass

    hh = int(total_h)
    mm = int((total_h - hh) * 60)

    await update.message.reply_text(
        f"📆 {month} oylik hisobot:\\n\\n"
        f"⏱ {hh} soat {mm} minut\\n"
        f"⭐ {int(total_b)} ball",
        reply_markup=main_keyboard()
    )

def main():
    if not BOT_TOKEN:
        raise RuntimeError("Missing BOT_TOKEN env var")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("oylik", monthly))
    app.add_handler(MessageHandler(filters.CONTACT, on_contact))
    app.add_handler(MessageHandler(filters.LOCATION, on_location))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    app.run_polling()

if __name__ == "__main__":
    main()
