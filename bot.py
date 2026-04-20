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
LAVA_SECRET_KEY = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1aWQiOiIwMDYyYTFmYy1mZmUzLTg3NjQtYzBmYi05YThmZjJiNmJlYzYiLCJ0aWQiOiJiOGU0ZTU4MS1lNGVmLWI3Y2ItM2U1Mi1mZGZjYjJmMjFiYzIifQ.dGr0qonEHDEA2IH0PnF_P4yWg8Po86HwOH-u02JxJgo
' 
WALLET_ID = 'R11597472' 

user_balances = {}

# --- FLASK ДЛЯ ПИНГА ---
app = Flask('')
@app.route('/')
def home(): return "LEVEL Bot (Telebot) Online"

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

Thread(target=run, daemon=True).start()

# --- ЛОГИКА БОТА ---
bot = telebot.TeleBot(TOKEN)

# 1. Создание счета (через requests)
def create_lava_invoice(user_id, amount):
    url = 'https://api.lava.ru/business/invoice/create'
    data = {"sum": amount, "walletId": WALLET_ID, "comment": f"user_{user_id}"}
    sign_str = f"{amount}:{WALLET_ID}"
    sign = hmac.new(LAVA_SECRET_KEY.encode(), sign_str.encode(), hashlib.sha256).hexdigest()
    
    try:
        resp = requests.post(url, json=data, headers={'Authorization': sign}, timeout=10)
        res = resp.json()
        if res.get('status') in [200, 201]:
            return res['data']['url'], res['data']['id']
    except:
        pass
    return None, None

# 2. Проверка статуса
def check_lava_status(invoice_id):
    url = 'https://api.lava.ru/business/invoice/status'
    data = {"invoiceId": invoice_id, "walletId": WALLET_ID}
    sign_str = f"{invoice_id}:{WALLET_ID}"
    sign = hmac.new(LAVA_SECRET_KEY.encode(), sign_str.encode(), hashlib.sha256).hexdigest()
    
    try:
        resp = requests.post(url, json=data, headers={'Authorization': sign}, timeout=10)
        res = resp.json()
        return res.get('data', {}).get('status') == 'success'
    except:
        return False

@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    balance = user_balances.get(uid, 0)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Пополнить на 100₽", callback_data="buy_100"))
    bot.send_message(message.chat.id, f"👋 Привет!\n💰 Твой баланс: {balance} руб.", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "buy_100")
def buy_callback(call):
    bot.answer_callback_query(call.id, "Создаю ссылку...")
    url, inv_id = create_lava_invoice(call.from_user.id, 100)
    
    if url:
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(
            types.InlineKeyboardButton("🔗 Оплатить (100₽)", url=url),
            types.InlineKeyboardButton("🔄 Проверить оплату", callback_data=f"check_{inv_id}")
        )
        bot.send_message(call.message.chat.id, "Оплатите и нажмите кнопку ниже:", reply_markup=kb)
    else:
        bot.send_message(call.message.chat.id, "❌ Ошибка API Lava.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('check_'))
def check_callback(call):
    inv_id = call.data.split('_')[1]
    if check_lava_status(inv_id):
        uid = call.from_user.id
        user_balances[uid] = user_balances.get(uid, 0) + 100
        bot.edit_message_text(f"✅ Баланс пополнен! Теперь: {user_balances[uid]} руб.", 
                              call.message.chat.id, call.message.message_id)
    else:
        bot.answer_callback_query(call.id, "❌ Оплата не найдена", show_alert=True)

if __name__ == '__main__':
    bot.infinity_polling()
