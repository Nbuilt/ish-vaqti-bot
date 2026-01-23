from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
import os
import datetime

import gspread
from google.oauth2.service_account import Credentials

# ================== TELEGRAM ==================
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise Exception("BOT_TOKEN topilmadi")

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
kb.add("🟢 Ish boshlandi", "🔴 Ish tugadi")

# ================== GOOGLE SHEETS ==================
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_file("google.json", scopes=SCOPES)
gc = gspread.authorize(creds)

sheet = gc.open("ISH_VAQTI").worksheet("RAW")

# ================== TEMP DATA ==================
user_gps = {}

# ================== HANDLERS ==================

@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    await msg.answer("Bot ishlayapti ✅\nTugmani bosing.", reply_markup=kb)

@dp.message_handler(lambda m: m.text == "🟢 Ish boshlandi")
async def start_work(msg: types.Message):
    await msg.answer("📍 Iltimos, lokatsiya yuboring")

@dp.message_handler(content_types=["location"])
async def get_location(msg: types.Message):
    lat = msg.location.latitude
    lon = msg.location.longitude
    user_gps[msg.from_user.id] = f"{lat},{lon}"
    await msg.answer("📸 Endi SELFIE yuboring")

@dp.message_handler(content_types=["photo"])
async def get_photo(msg: types.Message):
    user_id = msg.from_user.id
    name = msg.from_user.full_name
    now = datetime.datetime.now()

    gps = user_gps.get(user_id, "NA")
    file_id = msg.photo[-1].file_id

    sheet.append_row([
        str(user_id),
        name,
        now.strftime("%Y-%m-%d"),
        now.strftime("%H:%M:%S"),
        "🟢 Ish boshlandi",
        gps,
        file_id
    ])

    await msg.answer("✅ Ish boshlandi\n📊 Ma’lumot Sheet’ga yozildi")

@dp.message_handler(lambda m: m.text == "🔴 Ish tugadi")
async def end_work(msg: types.Message):
    now = datetime.datetime.now()
    sheet.append_row([
        str(msg.from_user.id),
        msg.from_user.full_name,
        now.strftime("%Y-%m-%d"),
        now.strftime("%H:%M:%S"),
        "🔴 Ish tugadi",
        "",
        ""
    ])
    await msg.answer("✅ Ish tugadi\n📊 Sheet’ga yozildi")

executor.start_polling(dp)
