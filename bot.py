import os, json
from datetime import datetime
import pytz
import gspread
from google.oauth2.service_account import Credentials
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# ================== SETTINGS ==================
TZ = pytz.timezone("Asia/Tashkent")

BOT_TOKEN = os.getenv("BOT_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")

ws_raw = None
ws_access = None

# ================== TIME ==================
def now():
    dt = datetime.now(TZ)
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S")

def to_dt(sana, vaqt):
    return TZ.localize(datetime.strptime(f"{sana} {vaqt}", "%Y-%m-%d %H:%M:%S"))

def diff_minutes(a, b):
    return int((a - b).total_seconds() / 60)

# ================== KEYBOARD ==================
def main_keyboard():
    return ReplyKeyboardMarkup(
        [["🟢 Ish boshlandi", "🔴 Ish tugadi"]],
        resize_keyboard=True
    )

# ================== SHEETS ==================
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

# ================== ACCESS ==================
def get_user_by_id(tg_id):
    rows = ws_access.get_all_records()
    for r in rows:
        if str(r["ID_Raqami"]) == str(tg_id):
            return r
    return None

def has_open_start(user_id, sana):
    rows = ws_raw.get_all_values()
    for i in range(1, len(rows)):
        if rows[i][0] == str(user_id) and rows[i][4] == sana and rows[i][6] == "":
            return True
    return False

# ================== COMMAND ==================
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

# ================== TEXT ==================
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ws_raw is None:
        connect()

    txt = update.message.text
    user = context.user_data.get("user")

    if not user:
        await update.message.reply_text("⛔ /start bosing")
        return

    sana, vaqt = now()

    # ===== ISH BOSHLANDI =====
    if txt == "🟢 Ish boshlandi":
        if has_open_start(user["ID_Raqami"], sana):
            await update.message.reply_text("❗ Bugun ish allaqachon boshlangan")
            return

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
        await update.message.reply_text("✅ Ish boshlandi")
        return

    # ===== ISH TUGADI =====
    if txt == "🔴 Ish tugadi":
        rows = ws_raw.get_all_values()

        for i in range(len(rows)-1, 0, -1):
            r = rows[i]
            if r[0] == str(user["ID_Raqami"]) and r[6] == "":
                ws_raw.update_cell(i+1, 7, vaqt)

                started = to_dt(r[4], r[5])
                finished = to_dt(r[4], vaqt)

                norma_start = to_dt(r[4], user["Norma_start"])
                norma_end = to_dt(r[4], user["Norma_end"])

                worked = diff_minutes(finished, started)
                late = max(0, diff_minutes(started, norma_start))
                early = max(0, diff_minutes(norma_start, started))
                overtime = max(0, diff_minutes(finished, norma_end))

                await update.message.reply_text(
                    f"🏁 Ish tugadi\n\n"
                    f"⏱ Ishlangan vaqt: {worked//60} soat {worked%60} minut\n"
                    f"⏰ Kech kelish: {late} minut\n"
                    f"🚀 Erta kelish: {early} minut\n"
                    f"🌙 Kech ketish: {overtime} minut"
                )
                return

        await update.message.reply_text("❗ Avval ish boshlanmagan")

# ================== MAIN ==================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    app.run_polling()

if __name__ == "__main__":
    main()