import os, json, re
from datetime import datetime
import pytz
import gspread
from google.oauth2.service_account import Credentials
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# ================== CONFIG ==================
TZ = pytz.timezone("Asia/Tashkent")

BOT_TOKEN = os.getenv("BOT_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")

ws_raw = None

# ================== HELPERS ==================
def normalize_phone(p: str) -> str:
    if not p:
        return ""
    d = re.sub(r"\D", "", p)
    if d.startswith("998"):
        return "+" + d
    if d.startswith("8"):
        return "+" + d[1:]
    return "+" + d

def now():
    dt = datetime.now(TZ)
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S")

# ================== SHEETS ==================
def get_gc():
    creds = Credentials.from_service_account_info(
        json.loads(GOOGLE_CREDS_JSON),
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return gspread.authorize(creds)

def get_sheet(name):
    gc = get_gc()
    sh = gc.open_by_key(SHEET_ID)
    return sh.worksheet(name)

def is_active_phone(phone):
    rows = get_sheet("ACCESS_LIST").get_all_records()
    for r in rows:
        if normalize_phone(r["Telefon"]) == phone and str(r["Aktiv"]).upper() == "TRUE":
            return True
    return False

# ================== KEYBOARDS ==================
def phone_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📞 Telefonni yuborish", request_contact=True)]],
        resize_keyboard=True
    )

def main_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["🟢 Ish boshlandi", "🔴 Ish tugadi"],
            ["🏗️ Yangi mijoz"]
        ],
        resize_keyboard=True
    )

# ================== COMMANDS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Telefon raqamingizni yuboring 👇",
        reply_markup=phone_keyboard()
    )

# ================== AUTH ==================
async def on_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = normalize_phone(update.message.contact.phone_number)

    if not is_active_phone(phone):
        await update.message.reply_text("⛔ Sizga ruxsat yo‘q")
        return

    context.user_data["phone"] = phone
    context.user_data["authorized"] = True

    await update.message.reply_text(
        "✅ Ruxsat berildi",
        reply_markup=main_keyboard()
    )

# ================== TEXT HANDLER ==================
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("authorized"):
        await update.message.reply_text(
            "Avval telefon yuboring",
            reply_markup=phone_keyboard()
        )
        return

    txt = update.message.text
    phone = context.user_data["phone"]
    sana, vaqt = now()

    raw_ws = get_sheet("RAW")

    # ---------- ISH BOSHLANDI ----------
    if txt == "🟢 Ish boshlandi":
        context.user_data["pending"] = "start"
        await update.message.reply_text("📍 Lokatsiya yuboring")
        return

    # ---------- ISH TUGADI ----------
    if txt == "🔴 Ish tugadi":
        rows = raw_ws.get_all_values()
        for i in range(len(rows)-1, 0, -1):
            r = rows[i]
            if normalize_phone(r[1]) == phone and r[6] == "":
                raw_ws.update_acell(f"G{i+1}", vaqt)
                await update.message.reply_text("✅ Ish tugadi", reply_markup=main_keyboard())
                return

        await update.message.reply_text("❗ Avval Ish boshlandi bosing")
        return

    # ---------- YANGI MIJOZ ----------
    if txt == "🏗️ Yangi mijoz":
        context.user_data["step"] = "client_id"
        await update.message.reply_text("Mijoz ID ni kiriting:")
        return

    # ---------- MIJOZ STEP-BY-STEP ----------
    step = context.user_data.get("step")
    if step:
        if step == "client_id":
            context.user_data["client_id"] = txt
            context.user_data["step"] = "client_name"
            await update.message.reply_text("Mijoz familyasi / ismi:")
            return

        if step == "client_name":
            context.user_data["client_name"] = txt
            context.user_data["step"] = "start_date"
            await update.message.reply_text("Boshlangan sana (YYYY-MM-DD):")
            return

        if step == "start_date":
            context.user_data["start_date"] = txt
            context.user_data["step"] = "building"
            await update.message.reply_text("Bino turi:")
            return

        if step == "building":
            context.user_data["building"] = txt
            context.user_data["step"] = "address"
            await update.message.reply_text("Manzil:")
            return

        if step == "address":
            get_sheet("CLIENT_SETTINGS").append_row([
                context.user_data["client_id"],
                context.user_data["client_name"],
                context.user_data["start_date"],
                context.user_data["building"],
                txt
            ])
            context.user_data.clear()
            await update.message.reply_text("✅ Mijoz qo‘shildi", reply_markup=main_keyboard())
            return

    await update.message.reply_text("Tugmalardan foydalaning 👇", reply_markup=main_keyboard())

# ================== LOCATION ==================
async def on_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("pending") != "start":
        return

    phone = context.user_data["phone"]
    user = update.effective_user
    sana, vaqt = now()

    get_sheet("RAW").append_row([
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

# ================== MAIN ==================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.CONTACT, on_contact))
    app.add_handler(MessageHandler(filters.LOCATION, on_location))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    app.run_polling()

if __name__ == "__main__":
    main()
