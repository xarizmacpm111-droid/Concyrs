import os
import logging
import hashlib
import hmac
import aiohttp
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.getenv('BOT_TOKEN') # Вставляем в Render
LAVA_SECRET_KEY = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1aWQiOiIwMDYyYTFmYy1mZmUzLTg3NjQtYzBmYi05YThmZjJiNmJlYzYiLCJ0aWQiOiJiOGU0ZTU4MS1lNGVmLWI3Y2ItM2U1Mi1mZGZjYjJmMjFiYzIifQ.dGr0qonEHDEA2IH0PnF_P4yWg8Po86HwOH-u02JxJgo
' 
WALLET_ID = 'R11597472' 

# Временное хранилище баланса (сбросится при перезагрузке Render)
user_balances = {}

# --- FLASK (ДЛЯ ПИНГА И РАБОТЫ ПОРТА) ---
app = Flask('')
@app.route('/')
def home(): return "LEVEL Bot Online"

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

Thread(target=run, daemon=True).start()

# --- ЛОГИКА БОТА ---
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
logging.basicConfig(level=logging.INFO)

# 1. Создание счета
async def create_lava_invoice(user_id, amount):
    url = 'https://api.lava.ru/business/invoice/create'
    data = {"sum": amount, "walletId": WALLET_ID, "comment": f"user_{user_id}"}
    # Подпись для безопасности
    sign_str = f"{amount}:{WALLET_ID}"
    sign = hmac.new(LAVA_SECRET_KEY.encode(), sign_str.encode(), hashlib.sha256).hexdigest()
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=data, headers={'Authorization': sign}) as resp:
            res = await resp.json()
            if res.get('status') in [200, 201]:
                return res['data']['url'], res['data']['id']
            return None, None

# 2. Проверка статуса счета
async def check_lava_status(invoice_id):
    url = 'https://api.lava.ru/business/invoice/status'
    data = {"invoiceId": invoice_id, "walletId": WALLET_ID}
    sign_str = f"{invoice_id}:{WALLET_ID}"
    sign = hmac.new(LAVA_SECRET_KEY.encode(), sign_str.encode(), hashlib.sha256).hexdigest()
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=data, headers={'Authorization': sign}) as resp:
            res = await resp.json()
            # Проверяем, что статус именно 'success'
            return res.get('data', {}).get('status') == 'success'

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    uid = message.from_user.id
    balance = user_balances.get(uid, 0)
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("Пополнить баланс на 100₽", callback_data="buy_100"))
    await message.answer(f"👋 Привет, {message.from_user.first_name}!\n💰 Твой баланс: {balance} руб.", reply_markup=kb)

@dp.callback_query_handler(text="buy_100")
async def buy_handler(callback: types.CallbackQuery):
    await callback.answer("Создаю ссылку...")
    url, inv_id = await create_lava_invoice(callback.from_user.id, 100)
    
    if url:
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(
            InlineKeyboardButton("🔗 Перейти к оплате (100₽)", url=url),
            InlineKeyboardButton("🔄 Я оплатил (Проверить)", callback_data=f"check_{inv_id}")
        )
        await callback.message.answer("Оплати счет по ссылке, затем нажми кнопку проверки:", reply_markup=kb)
    else:
        await callback.message.answer("❌ Ошибка API. Убедись, что ключ в коде верный.")

@dp.callback_query_handler(lambda c: c.data.startswith('check_'))
async def check_handler(callback: types.CallbackQuery):
    inv_id = callback.data.split('_')[1]
    is_paid = await check_lava_status(inv_id)
    
    if is_paid:
        uid = callback.from_user.id
        user_balances[uid] = user_balances.get(uid, 0) + 100
        await callback.message.edit_text(f"✅ Оплата подтверждена!\n💰 Твой новый баланс: {user_balances[uid]} руб.")
    else:
        await callback.answer("❌ Оплата еще не найдена. Попробуй через 30-60 секунд.", show_alert=True)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
