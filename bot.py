import os
import json
import datetime

import gspread
from google.oauth2.service_account import Credentials

from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor


# ===================== TELEGRAM =====================
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise Exception("BOT_TOKEN topilmadi (Railway Variables'ga qo'sh)")

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
kb.add("🟢 Ish boshlandi", "🔴 Ish tugadi")


# ===================== GOOGLE SHEETS =====================
SHEET_ID = os.environ.get("SHEET_ID")  # spreadsheet id (docs.google.com.../d/<ID>/edit)
if not SHEET_ID:
    raise Exception("SHEET_ID topilmadi (Railway Variables'ga qo'sh)")

TAB_NAME = os.environ.get("SHEET_TAB", "RAW")

creds_json = os.environ.get("GOOGLE_CREDS_JSON")
if not creds_json:
    raise Exception("GOOGLE_CREDS_JSON topilmadi (Railway Variables'ga qo'sh)")

creds_info = json.loads(creds_json)

# Faqat Sheets scope (Drive kerak emas!)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)

gc = gspread.authorize(creds)
sheet = gc.open_by_key(SHEET_ID).worksheet(TAB_NAME)


# ===================== TEMP DATA =====================
user_gps = {}     # user_id -> "lat,lon"
user_selfie = {}  # user_id -> telegram file_id


# ===================== HELPERS =====================
def now_date_time():
    now = datetime.datetime.now()
    return now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")


# ===================== HANDLERS =====================
@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    await msg.answer("Salom! Tugmani bosing:\n🟢 Ish boshlandi yoki 🔴 Ish tugadi", reply_markup=kb)


@dp.message_handler(lambda m: m.text == "🟢 Ish boshlandi")
async def start_work(msg: types.Message):
    await msg.answer("📍 Lokatsiya yuboring (Location).")
    await msg.answer(
        "Telefoningizda: 📎 (Attach) → Location → Send",
        reply_markup=types.ReplyKeyboardRemove()
    )


@dp.message_handler(content_types=["location"])
async def get_location(msg: types.Message):
    lat = msg.location.latitude
    lon = msg.location.longitude
    user_gps[msg.from_user.id] = f"{lat},{lon}"
    await msg.answer("📸 Endi selfie (rasm) yuboring.")


@dp.message_handler(content_types=["photo"])
async def get_photo(msg: types.Message):
    file_id = msg.photo[-1].file_id
    user_selfie[msg.from_user.id] = file_id

    sana, vaqt = now_date_time()
    uid = str(msg.from_user.id)
    ism = (msg.from_user.full_name or "").strip()
    gps = user_gps.get(msg.from_user.id, "")
    selfie = user_selfie.get(msg.from_user.id, "")

    # STATUS = Ish boshlandi
    sheet.append_row([uid, ism, sana, vaqt, "Ish boshlandi", gps, selfie])

    await msg.answer("✅ Ish boshlandi — Sheet'ga yozildi!", reply_markup=kb)


@dp.message_handler(lambda m: m.text == "🔴 Ish tugadi")
async def end_work(msg: types.Message):
    sana, vaqt = now_date_time()
    uid = str(msg.from_user.id)
    ism = (msg.from_user.full_name or "").strip()
    gps = user_gps.get(msg.from_user.id, "")
    selfie = user_selfie.get(msg.from_user.id, "")

    # STATUS = Ish tugadi
    sheet.append_row([uid, ism, sana, vaqt, "Ish tugadi", gps, selfie])

    await msg.answer("✅ Ish tugadi — Sheet'ga yozildi!", reply_markup=kb)


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
