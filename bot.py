from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add("🟢 Ish boshlandi", "🔴 Ish tugadi")

@dp.message_handler(commands=['start'])
async def start(msg):
    await msg.answer("Xush kelibsiz! Tugmani bosing.", reply_markup=keyboard)

@dp.message_handler(lambda m: m.text == "🟢 Ish boshlandi")
async def start_work(msg):
    await msg.answer("📍 Lokatsiya yuboring")

@dp.message_handler(content_types=['location'])
async def get_loc(msg):
    await msg.answer("📸 Endi selfie yuboring")

@dp.message_handler(content_types=['photo'])
async def get_photo(msg):
    await msg.answer("✅ Ish boshlandi tasdiqlandi")

@dp.message_handler(lambda m: m.text == "🔴 Ish tugadi")
async def end_work(msg):
    await msg.answer("✅ Ish tugadi qayd etildi")

executor.start_polling(dp)
