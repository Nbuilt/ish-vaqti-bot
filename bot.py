import os, json
from datetime import datetime, time
import pytz
import gspread
from google.oauth2.service_account import Credentials
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TZ = pytz.timezone("Asia/Tashkent")

BOT_TOKEN = os.getenv("BOT_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

ws = None

# ----------------- GOOGLE SHEETS -----------------
def get_ws():
    creds = Credentials.from_service_account_info(
        json.loads(GOOGLE_CREDS_JSON),
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return gspread.authorize(creds).open_by_key(SHEET_ID).worksheet("RAW_DATA")

def get_sheet(name):
    return ws.spreadsheet.worksheet(name)

# ----------------- TIME -----------------
def now():
    dt = datetime.now(TZ)
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S")

# ----------------- KEYBOARDS -----------------
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

# ----------------- AUTH -----------------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("authorized"):
        await update.message.reply_text("Bot tayyor.", reply_markup=main_keyboard())
    else:
        await update.message.reply_text(
            "Botdan foydalanish uchun telefon raqamingizni yuboring.",
            reply_markup=phone_keyboard()
        )

async def on_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ws
    if ws is None:
        ws = get_ws()

    phone = update.message.contact.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone

    access = get_sheet("ACCESS_LIST").col_values(1)
    if phone not in access:
        await update.message.reply_text("❌ Sizga ruxsat berilmagan.")
        return

    context.user_data["authorized"] = True
    context.user_data["phone"] = phone
    await update.message.reply_text("✅ Telefon tasdiqlandi.", reply_markup=main_keyboard())

# ----------------- HELPERS -----------------
def has_started_today(phone, sana):
    rows = ws.get_all_values()
    return any(r[1] == phone and r[4] == sana for r in rows[1:])

def find_today_row(phone, sana):
    rows = ws.get_all_values()
    for i in range(len(rows), 1, -1):
        r = rows[i-1]
        if r[1] == phone and r[4] == sana and r[6].strip() == "":
            return i
    return None

def get_today_stats(phone, sana):
    calc = get_sheet("CALC")
    rows = calc.get_all_values()
    hours = 0
    ball = 0
    for r in rows[1:]:
        if r[0] == phone and r[1] == sana:
            hours += float(r[4])
            ball += float(r[6])
    h = int(hours)
    m = int((hours - h) * 60)
    return h, m, int(ball)

# ----------------- TEXT -----------------
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("authorized"):
        await update.message.reply_text("📞 Avval telefon yuboring.", reply_markup=phone_keyboard())
        return

    txt = update.message.text
    phone = context.user_data["phone"]
    sana, vaqt = now()

    if txt == "🟢 Ish boshlandi":
        if has_started_today(phone, sana):
            await update.message.reply_text("❌ Bugun allaqachon bosilgan.", reply_markup=main_keyboard())
            return
        context.user_data["pending"] = "start"
        await update.message.reply_text("📍 Lokatsiya yuboring.")
        return

    if txt == "🔴 Ish tugadi":
        row = find_today_row(phone, sana)
        if not row:
            await update.message.reply_text("❗ Avval Ish boshlandi bosing.")
            return
        ws.update(f"G{row}", vaqt)

        h, m, ball = get_today_stats(phone, sana)
        warn = "\n⚠️ Ball minusda!" if ball < 0 else ""

        await update.message.reply_text(
            f"✅ Ish tugadi!\n\n"
            f"⏱ {h} soat {m} minut\n"
            f"⭐ Jami ball: {ball}{warn}\n\n"
            "📊 Ma’lumotlar Sheets’ga yozildi.",
            reply_markup=main_keyboard()
        )
        return

# ----------------- LOCATION -----------------
async def on_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    context.user_data.pop("pending")
    await update.message.reply_text("✅ Ish boshlandi yozildi.", reply_markup=main_keyboard())

# ----------------- MONTHLY -----------------
async def monthly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = context.user_data["phone"]
    month = datetime.now(TZ).strftime("%Y-%m")
    calc = get_sheet("CALC")

    h = b = 0
    for r in calc.get_all_values()[1:]:
        if r[0] == phone and r[1].startswith(month):
            h += float(r[4])
            b += float(r[6])

    await update.message.reply_text(
        f"📆 {month}\n⏱ {int(h)} soat\n⭐ {int(b)} ball"
    )

# ----------------- ADMIN REPORT -----------------
async def daily_admin(context: ContextTypes.DEFAULT_TYPE):
    calc = get_sheet("CALC")
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    msg = "📊 Bugungi hisobot:\n\n"

    for r in calc.get_all_values()[1:]:
        if r[1] == today:
            msg += f"{r[0]} → ⏱ {r[4]} | ⭐ {r[6]}\n"

    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=msg)

# ----------------- MAIN -----------------
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("oylik", monthly))
    app.add_handler(MessageHandler(filters.CONTACT, on_contact))
    app.add_handler(MessageHandler(filters.LOCATION, on_location))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    app.job_queue.run_daily(daily_admin, time=time(0, 0))

    app.run_polling()

if __name__ == "__main__":
    main()
