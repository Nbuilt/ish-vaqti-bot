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

SHEET_ID = os.getenv("SHEET_ID")          # like: 1zKQjhUh_Ms5KP7CwqSTYkkJMc70cgMkbEl5ydA3_o88
TAB_NAME = os.getenv("TAB_NAME", "RAW")   # default RAW

# Put the FULL content of google.json into this variable
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")

# Timezone (Uzbekistan)
TZ = pytz.timezone(os.getenv("TZ", "Asia/Tashkent"))

# Columns in sheet (RAW):
# A User ID | B Name | C Date | D Start | E End | F Daily hours | G GPS | H Points | I Status | J Photo ID


# ========= Google Sheets connect =========
def get_worksheet():
    if not GOOGLE_CREDS_JSON:
        raise RuntimeError("GOOGLE_CREDS_JSON is empty. Add it in Railway Variables.")

    creds_info = json.loads(GOOGLE_CREDS_JSON)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    gc = gspread.authorize(creds)

    sh = gc.open_by_key(SHEET_ID)
    return sh.worksheet(TAB_NAME)


ws = None

# ========= Simple state =========
pending = {}      # user_id -> "start" or "end"
temp_gps = {}     # user_id -> "lat,lon"
temp_photo = {}   # user_id -> file_id


def now_date_time():
    dt = datetime.now(TZ)
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S")


def build_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["🟢 Start", "🔴 End"],
            [KeyboardButton("📍 Send location", request_location=True)]
        ],
        resize_keyboard=True
    )


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salom! 🕒 Ish vaqtini yozish bot.\n\n"
        "1) 🟢 Start bos → lokatsiya yubor → (ixtiyoriy) selfie\n"
        "2) 🔴 End bos → lokatsiya yubor\n\n"
        "Keyboard pastda 👇",
        reply_markup=build_keyboard()
    )


def find_open_row(user_id: str, work_date: str):
    """
    Find last row where:
    A = user_id AND C = work_date AND E (End) is empty
    Returns row index (1-based) or None.
    """
    values = ws.get_all_values()
    # scan from bottom to top for speed
    for idx in range(len(values), 1, -1):
        row = values[idx - 1]
        a = row[0] if len(row) > 0 else ""
        c = row[2] if len(row) > 2 else ""
        e = row[4] if len(row) > 4 else ""
        if a == user_id and c == work_date and (e is None or str(e).strip() == ""):
            return idx
    return None


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ws
    if ws is None:
        ws = get_worksheet()

    text = (update.message.text or "").strip()
    user = update.effective_user
    user_id = str(user.id)
    name = (user.full_name or "").strip()

    if text == "🟢 Start":
        pending[user_id] = "start"
        temp_gps.pop(user_id, None)
        temp_photo.pop(user_id, None)
        await update.message.reply_text("📍 Lokatsiya yuboring (Send location).", reply_markup=build_keyboard())
        return

    if text == "🔴 End":
        pending[user_id] = "end"
        temp_gps.pop(user_id, None)
        await update.message.reply_text("📍 Lokatsiya yuboring (Send location).", reply_markup=build_keyboard())
        return

    await update.message.reply_text("🟢 Start yoki 🔴 End bosing.", reply_markup=build_keyboard())


async def on_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ws
    if ws is None:
        ws = get_worksheet()

    loc = update.message.location
    user = update.effective_user
    user_id = str(user.id)
    name = (user.full_name or "").strip()
    work_date, work_time = now_date_time()

    temp_gps[user_id] = f"{loc.latitude},{loc.longitude}"

    action = pending.get(user_id)
    if action == "start":
        # Ask selfie (optional) OR we can log immediately
        await update.message.reply_text("📸 Selfie yuborsangiz ham bo‘ladi (ixtiyoriy). Yoki 'OK' deb yozing.")
        return

    if action == "end":
        row_idx = find_open_row(user_id, work_date)
        if not row_idx:
            await update.message.reply_text("❗ Ochiq (yakunlanmagan) Start topilmadi. Avval 🟢 Start bosing.")
            return

        # Update End time, GPS, Status
        ws.update(f"E{row_idx}", work_time)
        ws.update(f"G{row_idx}", temp_gps.get(user_id, ""))
        ws.update(f"I{row_idx}", "✅ Completed")

        pending.pop(user_id, None)
        await update.message.reply_text("✅ Ish tugadi! End vaqti yozildi.", reply_markup=build_keyboard())
        return

    await update.message.reply_text("🟢 Start yoki 🔴 End bosing.", reply_markup=build_keyboard())


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ws
    if ws is None:
        ws = get_worksheet()

    user = update.effective_user
    user_id = str(user.id)
    name = (user.full_name or "").strip()
    work_date, work_time = now_date_time()

    file_id = update.message.photo[-1].file_id
    temp_photo[user_id] = file_id

    # Only meaningful if pending start
    if pending.get(user_id) != "start":
        await update.message.reply_text("📸 Rasm qabul qilindi, lekin Start bosilmagan.")
        return

    gps = temp_gps.get(user_id, "")
    # Append a new row with Start filled, End empty
    ws.append_row([user_id, name, work_date, work_time, "", "", gps, "", "❌ Incomplete", file_id])

    pending.pop(user_id, None)
    await update.message.reply_text("✅ Start yozildi! Ishni tugatsangiz 🔴 End bosing.", reply_markup=build_keyboard())


async def on_ok_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    If user does not want to send selfie, they can type OK after location for Start.
    """
    global ws
    if ws is None:
        ws = get_worksheet()

    user = update.effective_user
    user_id = str(user.id)
    name = (user.full_name or "").strip()
    work_date, work_time = now_date_time()

    if pending.get(user_id) == "start":
        gps = temp_gps.get(user_id, "")
        ws.append_row([user_id, name, work_date, work_time, "", "", gps, "", "❌ Incomplete", ""])
        pending.pop(user_id, None)
        await update.message.reply_text("✅ Start yozildi! (selfiesiz)", reply_markup=build_keyboard())


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is empty. Add it in Railway Variables.")
    if not SHEET_ID:
        raise RuntimeError("SHEET_ID is empty. Add it in Railway Variables.")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^(OK|ok|Ok)$"), on_ok_text))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(MessageHandler(filters.LOCATION, on_location))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))

    app.run_polling()


if __name__ == "__main__":
    main()
