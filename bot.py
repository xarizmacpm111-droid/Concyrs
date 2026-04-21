import os
import telebot
import hashlib
import hmac
import requests
from flask import Flask
from threading import Thread
from telebot import types

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.getenv('BOT_TOKEN')
# Вставь свой длинный ключ между кавычек
LAVA_SECRET_KEY = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1aWQiOiIwMDYyYTFmYy1mZmUzLTg3NjQtYzBmYi05YThmZjJiNmJlYzYiLCJ0aWQiOiJlOGRhZDZiNy00MmE5LWJkZmUtMzdmNy04N2Q4MTE4ODNiNmQifQ.8-Qk2yDIaowt-3bjjO1rMl8f9h2SJh_qV8jBPgXbWxc' 
WALLET_ID = 'R11597472' 

user_balances = {}

# --- FLASK ДЛЯ РАБОТЫ 24/7 ---
app = Flask('')
@app.route('/')
def home(): return "LEVEL Bot is Live"

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

Thread(target=run, daemon=True).start()

# --- ЛОГИКА БОТА ---
bot = telebot.TeleBot(TOKEN)

def create_lava_invoice(user_id, amount):
    url = 'https://api.lava.ru/business/invoice/create'
    amount = float(amount)
    # Очищаем ключ от пробелов и переносов
    clean_key = LAVA_SECRET_KEY.strip().replace('\n', '').replace('\r', '').replace(' ', '')
    
    data = {
        "sum": amount,
        "walletId": WALLET_ID,
        "comment": f"user_{user_id}"
    }
    
    # Формируем подпись по стандарту: сумма:кошелек
    sign_str = f"{amount}:{WALLET_ID}"
    sign = hmac.new(clean_key.encode(), sign_str.encode(), hashlib.sha256).hexdigest()
    
    try:
        headers = {
            'Authorization': sign,
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        resp = requests.post(url, json=data, headers=headers, timeout=15)
        res = resp.json()
        
        # Печатаем ответ в логи Render (вкладка Logs)
        print(f"LAVA RESPONSE: {res}")
        
        if res.get('status') in [200, 201, 'success']:
            return res['data']['url'], res['data']['id']
    except Exception as e:
        print(f"LAVA CONNECTION ERROR: {e}")
    return None, None

@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    balance = user_balances.get(uid, 0)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Пополнить на 100₽", callback_data="buy_100"))
    bot.send_message(message.chat.id, f"👋 Привет!\n💰 Твой баланс: {balance} руб.", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "buy_100")
def buy_callback(call):
    bot.answer_callback_query(call.id, "Генерирую счет...")
    url, inv_id = create_lava_invoice(call.from_user.id, 100)
    
    if url:
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(
            types.InlineKeyboardButton("🔗 Оплатить (100₽)", url=url),
            types.InlineKeyboardButton("🔄 Проверить оплату", callback_data=f"check_{inv_id}")
        )
        bot.send_message(call.message.chat.id, "Нажмите кнопку для оплаты:", reply_markup=kb)
    else:
        bot.send_message(call.message.chat.id, "❌ Ошибка создания счета. Проверь Logs в Render.")

if __name__ == '__main__':
    print("LEVEL Bot Started")
    bot.infinity_polling()
