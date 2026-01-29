import os, json
from datetime import datetime
import pytz
import gspread
from google.oauth2.service_account import Credentials
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TZ = pytz.timezone("Asia/Tashkent")

BOT_TOKEN = os.getenv("BOT_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")

ws_raw = None
ws_access = None

# ================= TIME =================
def now():
    dt = datetime.now(TZ)
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S")

# ================= KEYBOARD =================
def main_keyboard():
    return ReplyKeyboardMarkup(
        [["🟢 Ish boshlandi", "🔴 Ish tugadi"]],
        resize_keyboard=True
    )

# ================= SHEETS =================
def connect():
    global ws_raw, ws_access
    creds = Credentials.from_service_account_info(
        json.loads(GOOGLE_CREDS_JSON),
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)
    ws_raw = sh.worksheet("RAW")
    ws_access = sh.worksheet("ACCESS_LIST")

# ================= ACCESS =================
def get_user_by_id(tg_id):
    rows = ws_access.get_all_records()
    for r in rows:
        if str(r["ID_Raqami"]) == str(tg_id):
            return r
    return None

# ================= COMMANDS =================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ws_raw is None:
        connect()

    tg_id = update.effective_user.id
    user = get_user_by_id(tg_id)

    if not user:
        await update.message.reply_text("⛔ Sizga ruxsat yo‘q")
        return

    context.user_data["user"] = user
    await update.message.reply_text(
        f"Xush kelibsiz {user['Name']} 👋",
        reply_markup=main_keyboard()
    )

# ================= TEXT =================
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ws_raw is None:
        connect()

    txt = update.message.text
    user = context.user_data.get("user")

    if not user:
        await update.message.reply_text("⛔ /start bosing")
        return

    sana, vaqt = now()

    if txt == "🟢 Ish boshlandi":
        ws_raw.append_row([
            user["ID_Raqami"],
            user["Surname"],
            user["Name"],
            user["Mobile_number"],
            sana,
            vaqt,
            "",
            "BOR",
            update.effective_user.id
        ])
        await update.message.reply_text("✅ Ish boshlandi yozildi")
        return

    if txt == "🔴 Ish tugadi":
        rows = ws_raw.get_all_values()
        for i in range(len(rows)-1, 0, -1):
            if rows[i][0] == str(user["ID_Raqami"]) and rows[i][6] == "":
                ws_raw.update_cell(i+1, 7, vaqt)
                await update.message.reply_text("🏁 Ish tugadi yozildi")
                return

        await update.message.reply_text("❗ Avval ish boshlanmagan")

# ================= MAIN =================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    app.run_polling()

if __name__ == "__main__":
    main()
