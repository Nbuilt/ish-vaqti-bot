from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
import os

TOKEN = os.environ.get("BOT_TOKEN")

if not TOKEN:
    raise Exception("BOT_TOKEN topilmadi")

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
kb.add("🟢 Ish boshlandi", "🔴 Ish tugadi")

@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    await msg.answer("Bot ishlayapti ✅", reply_markup=kb)

@dp.message_handler(lambda m: m.text == "🟢 Ish boshlandi")
async def start_work(msg: types.Message):
    await msg.answer("📍 Lokatsiya yuboring")

@dp.message_handler(content_types=["location"])
async def loc(msg: types.Message):
    await msg.answer("📸 Selfie yuboring")

@dp.message_handler(content_types=["photo"])
async def photo(msg: types.Message):
    await msg.answer("✅ Ish boshlandi")

@dp.message_handler(lambda m: m.text == "🔴 Ish tugadi")
async def end(msg: types.Message):
    await msg.answer("✅ Ish tugadi")

executor.start_polling(dp)
