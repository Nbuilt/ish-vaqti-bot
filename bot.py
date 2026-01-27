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

# ================= PHONE =================
def normalize_phone(p: str) -> str:
    if not p:
        return ""
    digits = re.sub(r"\D", "", p)
    if not digits:
        return ""
    if digits.startswith("998"):
        return "+" + digits
    if digits.startswith("8") and len(digits) > 10:
        return "+" + digits[1:]
    return "+" + digits

# ================= TIME =================
def now():
    dt = datetime.now(TZ)
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S")

# ================= KEYBOARD =================
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

# ================= SHEETS =================
def get_ws():
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

# ================= HELPERS =================
def has_started_today(phone, sana):
    rows = ws.get_all_values()
    for r in rows[1:]:
        if len(r) > 4 and normalize_phone(r[1]) == phone and r[4] == sana:
            return True
    return False

def find_last_open_row(phone, sana):
    rows = ws.get_all_values()
    for i in range(len(rows), 1, -1):
        r = rows[i-1]
        if len(r) >= 7 and normalize_phone(r[1]) == phone and r[4] == sana and str(r[6]).strip() == "":
            return i
    return None

def get_today_stats(phone, sana):
    calc = get_sheet("CALC")
    rows = calc.get_all_values()
    hours = 0
    ball = 0
    for r in rows[1:]:
        if len(r) > 6 and normalize_phone(r[0]) == phone and r[1] == sana:
            try: hours += float(r[4])
            except: pass
            try: ball += float(r[6])
            except: pass
    h = int(hours)
    m = int((hours - h) * 60)
    return h, m, int(ball)

# ================= COMMANDS =================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ws
    if ws is None:
        ws = get_ws()

    if context.user_data.get("authorized"):
        await update.message.reply_text("Bot tayyor ✅", reply_markup=main_keyboard())
    else:
        await update.message.reply_text(
            "Telefon raqamingizni yuboring",
            reply_markup=phone_keyboard()
        )

# ===== CONTACT OR TEXT PHONE =====
async def on_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await authorize_phone(update.message.contact.phone_number, update, context)

async def authorize_phone(raw_phone, update, context):
    global ws
    if ws is None:
        ws = get_ws()

    phone = normalize_phone(raw_phone)
    allowed = allowed_phones_set()

    if phone not in allowed:
        await update.message.reply_text(f"❌ Ruxsat yo‘q: {phone}")
        return

    context.user_data["authorized"] = True
    context.user_data["phone"] = phone

    await update.message.reply_text(
        "✅ Telefon tasdiqlandi",
        reply_markup=main_keyboard()
    )

# ================= TEXT =================
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ws
    if ws is None:
        ws = get_ws()

    txt = (update.message.text or "").strip()

    # 🔥 TEXT PHONE ACCEPT
    if not context.user_data.get("authorized"):
        maybe_phone = normalize_phone(txt)
        if len(maybe_phone) >= 12:
            await authorize_phone(maybe_phone, update, context)
            return

        await update.message.reply_text(
            "📞 Avval telefon raqamingizni yuboring",
            reply_markup=phone_keyboard()
        )
        return

    phone = context.user_data["phone"]
    sana, vaqt = now()

    if txt == "🟢 Ish boshlandi":
        if has_started_today(phone, sana):
            await update.message.reply_text("❌ Bugun start bosilgan")
            return
        context.user_data["pending"] = "start"
        await update.message.reply_text("📍 Lokatsiya yuboring")
        return

    if txt == "🔴 Ish tugadi":
        row = find_last_open_row(phone, sana)
        if not row:
            await update.message.reply_text("❗ Avval Ish boshlandi bosing")
            return

        ws.update_acell(f"G{row}", vaqt)

        h, m, ball = get_today_stats(phone, sana)
        await update.message.reply_text(
            f"✅ Ish tugadi\n⏱ {h} soat {m} min\n⭐ Ball: {ball}",
            reply_markup=main_keyboard()
        )
        return

    await update.message.reply_text("Tugmalardan foydalaning 👇", reply_markup=main_keyboard())

# ================= LOCATION =================
async def on_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ws
    if ws is None:
        ws = get_ws()

    if context.user_data.get("pending") != "start":
        return

    phone = context.user_data["phone"]
    user = update.effective_user
    sana, vaqt = now()

    ws.append_row([
        str(user.id),
        phone,
        user.last_name or "",
        user.first_name or "",
        sana,
        vaqt,
        "",
        "bor"
    ])

    context.user_data.pop("pending", None)

    await update.message.reply_text("✅ Ish boshlandi yozildi", reply_markup=main_keyboard())

# ================= MAIN =================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.CONTACT, on_contact))
    app.add_handler(MessageHandler(filters.LOCATION, on_location))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    app.run_polling()

if __name__ == "__main__":
    main()
