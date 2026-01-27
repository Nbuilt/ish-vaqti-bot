import os
import json
from datetime import datetime
import pytz

import gspread
from google.oauth2.service_account import Credentials

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters


# ========= SETTINGS (Railway Variables) =========
BOT_TOKEN = os.getenv("BOT_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
TAB_NAME = os.getenv("TAB_NAME", "RAW_DATA")
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")

TZ = pytz.timezone("Asia/Tashkent")


# ========= Google Sheets =========
def get_ws():
    creds_info = json.loads(GOOGLE_CREDS_JSON)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    gc = gspread.authorize(creds)
    return gc.open_by_key(SHEET_ID).worksheet(TAB_NAME)


ws = None
pending = {}   # user_id -> start/end
temp_gps = {} # user_id -> "bor"


def now():
    dt = datetime.now(TZ)
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S")


def keyboard():
    return ReplyKeyboardMarkup(
        [
            ["🟢 Ish boshlandi", "🔴 Ish tugadi"],
            [KeyboardButton("📍 Lokatsiya yuborish", request_location=True)]
        ],
        resize_keyboard=True
    )


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salom! Ish vaqtini yozish bot.\n\n"
        "🟢 Ish boshlandi → lokatsiya yubor\n"
        "🔴 Ish tugadi → lokatsiya yubor",
        reply_markup=keyboard()
    )


def find_today_row(user_id, sana):
    rows = ws.get_all_values()
    for i in range(len(rows), 1, -1):
        r = rows[i-1]
        if r[0] == user_id and r[4] == sana and r[6] == "":
            return i
    return None


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ws
    if ws is None:
        ws = get_ws()

    txt = update.message.text
    user = update.effective_user
    uid = str(user.id)

    if txt in ["🟢 Ish boshlandi", "🟢 Start"]:
    pending[uid] = "start"
    await update.message.reply_text(
        "📍 Lokatsiya yuboring",
        reply_markup=keyboard()
    )
    return

if txt in ["🔴 Ish tugadi", "🔴 End"]:
    pending[uid] = "end"
    await update.message.reply_text(
        "📍 Lokatsiya yuboring",
        reply_markup=keyboard()
    )
    return

    await update.message.reply_text("Tugmalardan foydalaning 👇", reply_markup=keyboard())


async def on_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ws
    if ws is None:
        ws = get_ws()

    user = update.effective_user
    uid = str(user.id)
    loc = update.message.location
    sana, vaqt = now()

    familya = user.last_name or ""
    ism = user.first_name or ""

    action = pending.get(uid)

    if action == "start":
        ws.append_row([
            uid,
            "",
            familya,
            ism,
            sana,
            vaqt,
            "",
            "bor"
        ])
        pending.pop(uid, None)
        await update.message.reply_text("✅ Ish boshlandi yozildi", reply_markup=keyboard())
        return

    if action == "end":
        row = find_today_row(uid, sana)
        if not row:
            await update.message.reply_text("❗ Avval Ish boshlandi bosing")
            return

        ws.update(f"G{row}", vaqt)
        ws.update(f"H{row}", "bor")
        pending.pop(uid, None)
        await update.message.reply_text("✅ Ish tugadi yozildi", reply_markup=keyboard())
        return


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.LOCATION, on_location))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.run_polling()


if __name__ == "__main__":
    main()
