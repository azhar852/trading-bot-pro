from datetime import datetime
import os
import sqlite3
import threading
import time
from flask import Flask, request
import requests

# Auto-install external packages if missing
try:
  import yfinance as yf
except ImportError:
  os.system('pip install yfinance')
  import yfinance as yf

try:
  import feedparser
except ImportError:
  os.system('pip install feedparser')
  import feedparser

app = Flask(__name__)

# Hardcoded token hata kar environment variable se secure kar diya gaya hai
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
RENDER_URL = 'https://trading-bot-3-rkcp.onrender.com'
CHANNEL_USERNAME = '@AapkaChannelUsername'

LAST_SIGNAL_STATE = None
PROCESSED_UPDATE_IDS = set()


def init_db():
  conn = sqlite3.connect('bot_users.db')
  cursor = conn.cursor()
  cursor.execute(
      '''CREATE TABLE IF NOT EXISTS users (chat_id INTEGER PRIMARY KEY)'''
  )
  cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            symbol TEXT,
            entry_price REAL,
            exit_price REAL,
            qty INTEGER,
            pnl REAL,
            date TEXT
        )
    ''')
  conn.commit()
  conn.close()


init_db()


def add_user_to_db(chat_id):
  try:
    conn = sqlite3.connect('bot_users.db')
    cursor = conn.cursor()
    cursor.execute(
        'INSERT OR IGNORE INTO users (chat_id) VALUES (?)', (chat_id,)
    )
    conn.commit()
    conn.close()
  except Exception as e:
    print(f'DB Error: {e}')


def get_all_users():
  users = set()
  try:
    conn = sqlite3.connect('bot_users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT chat_id FROM users')
    rows = cursor.fetchall()
    for row in rows:
      users.add(row[0])
    conn.close()
  except Exception as e:
    print(f'DB Read Error: {e}')
  return users


def check_user_subscription(chat_id):
  if not TELEGRAM_BOT_TOKEN:
    return True
  url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getChatMember?chat_id={CHANNEL_USERNAME}&user_id={chat_id}'
  try:
    response = requests.get(url, timeout=5)
    if response.status_code == 200:
      data = response.json()
      if data.get('ok'):
        status = data['result'].get('status')
        if status in ['member', 'administrator', 'creator']:
          return True
  except Exception as e:
    print(f'FSub check error: {e}')
  return False


def get_main_keyboard():
  return {
      'inline_keyboard': [
          [
              {'text': '📰 News', 'callback_data': 'news'},
              {'text': '🔄 Reversal', 'callback_data': 'reversal'},
          ],
          [
              {'text': '🎯 Trend', 'callback_data': 'trend'},
              {'text': '📊 Nifty', 'callback_data': 'nifty'},
          ],
          [
              {'text': '🏦 BankNifty', 'callback_data': 'banknifty'},
              {'text': '📈 Sensex', 'callback_data': 'sensex'},
          ],
          [
              {'text': '📐 Pivots', 'callback_data': 'pivots'},
              {'text': '📈 PCR', 'callback_data': 'pcr'},
          ],
          [
              {'text': '🐋 BigMoney', 'callback_data': 'bigmoney'},
              {'text': '🛢️ Commodity', 'callback_data': 'commodity'},
          ],
          [
              {'text': '🤖 AI Analysis', 'callback_data': 'ai_analysis'},
              {'text': '📋 Summary', 'callback_data': 'summary'},
          ],
          [
              {'text': '🧮 Calculator (/calc)', 'callback_data': 'calc_help'},
              {
                  'text': '📖 Trade Journal (/trade)',
                  'callback_data': 'trade_help',
              },
          ],
          [
              {'text': '⚙️ Support & Reg', 'callback_data': 'support'},
              {'text': '⚡ Signal', 'callback_data': 'signal'},
          ],
      ]
  }


@app.route('/')
def home():
  return 'MyMarketAlertBot Ultimate Pro Webhook Active!'


@app.route('/webhook', methods=['POST'])
def telegram_webhook():
  try:
    update = request.get_json()
    if not update:
      return 'OK', 200

    update_id = update.get('update_id')
    if update_id:
      if update_id in PROCESSED_UPDATE_IDS:
        return 'OK', 200
      PROCESSED_UPDATE_IDS.add(update_id)
      if len(PROCESSED_UPDATE_IDS) > 300:
        PROCESSED_UPDATE_IDS.clear()

    chat_id = None
    if 'callback_query' in update:
      chat_id = update['callback_query']['message']['chat']['id']
    elif 'message' in update:
      chat_id = update['message'].get('chat', {}).get('id')

    if chat_id:
      add_user_to_db(chat_id)

      if not check_user_subscription(chat_id):
        join_keyboard = {
            'inline_keyboard': [[{
                'text': '📢 Join Channel Now',
                'url': f'https://t.me/{CHANNEL_USERNAME.lstrip("@")}',
            }]]
        }
        send_telegram_message(
            chat_id,
            '🚀 *To use this bot, you must join our channel first!*'
            '\n\nPlease join the channel using the button below and then press'
            ' /start again.',
            reply_markup=join_keyboard,
        )
        if 'callback_query' in update:
          answer_callback_query(update['callback_query']['id'])
        return 'OK', 200

    if 'callback_query' in update:
      cq = update['callback_query']
      answer_callback_query(cq['id'])
      data_action = cq['data']
      process_action(chat_id, data_action)
      return 'OK', 200

    message = update.get('message', {})
    text = message.get('text', '').strip()
    text_lower = text.lower()

    if text_lower in ['/start', 'start']:
      send_telegram_message(
          chat_id,
          '✅ *MyMarketAlertBot Ultimate Pro Active!*\n\nAll Indices, Pivots,'
          ' AI Analysis, Support Registration & Signals Ready.\n\n💡 *Commands:*\n•'
          ' `/calc <entry>` - Target & Stoploss\n• `/trade <symbol> <entry>'
          ' <exit> <qty>` - Save Trade P&L\n\nSelect a command using the buttons'
          ' below:',
          reply_markup=get_main_keyboard(),
      )
    elif text_lower.startswith('/calc'):
      try:
        parts = text.split()
        entry = float(parts[1])
        sl = entry * 0.99
        target1 = entry + (entry - sl) * 2
        target2 = entry + (entry - sl) * 3
        calc_msg = (
            '🎯 *Trade Calculator Setup*\n'
            f'• Entry Price: `{entry}`\n'
            f'• 🔴 Stop Loss: `{sl:.2f}`\n'
            f'• 🟢 Target 1 (1:2): `{target1:.2f}`\n'
            f'• 🟢 Target 2 (1:3): `{target2:.2f}`'
        )
        send_telegram_message(chat_id, calc_msg)
      except Exception:
        send_telegram_message(
            chat_id, '⚠️ Sahi format use karein: `/calc 22600`'
        )
    elif text_lower.startswith('/trade'):
      try:
        parts = text.split()
        symbol = parts[1]
        entry = float(parts[2])
        exit_p = float(parts[3])
        qty = int(parts[4])
        pnl = (exit_p - entry) * qty

        conn = sqlite3.connect('bot_users.db')
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO trades (chat_id, symbol, entry_price, exit_price, qty,'
            ' pnl, date) VALUES (?, ?, ?, ?, ?, ?, datetime("now"))',
            (chat_id, symbol, entry, exit_p, qty, pnl),
        )
        conn.commit()
        conn.close()

        trade_msg = (
            '✅ *Trade Successfully Saved!*\n'
            f'• Symbol: `{symbol}`\n'
            f'• P&L: `₹{pnl:.2f}`'
        )
        send_telegram_message(chat_id, trade_msg)
      except Exception:
        send_telegram_message(
            chat_id,
            '⚠️ Sahi format use karein: `/trade Nifty 22600 22750 50`',
        )
    elif text_lower == '/news':
      send_telegram_message(chat_id, get_market_news())
    elif text_lower == '/reversal':
      rev = check_reversal_pattern('^NSEI')
      tr = get_live_market_trend('^NSEI')
      if rev:
        msg_rev = (
            '🔄 *LIVE REVERSAL*\n'
            f"• {rev['status']}\n"
            f"• Price: `{rev['price']}`\n"
            f"💡 {rev['action']}"
        )
        send_telegram_message(chat_id, msg_rev)
      else:
        msg_norev = (
            '🔄 *REVERSAL CHECK*\n'
            f"• Trend: {tr['status']}\n"
            '⚖️ No immediate reversal.'
        )
        send_telegram_message(chat_id, msg_norev)
    elif text_lower.startswith('/ai'):
      query = text[3:].strip() or 'Overall market condition'
      send_telegram_message(chat_id, get_ai_trading_analysis(query))
    elif text_lower in ['/trend', '/market']:
      tr = get_live_market_trend('^NSEI')
      msg_trend = (
          '🎯 *LIVE TREND (NIFTY)*\n'
          f"• Price: `{tr['price']}` ({tr['change']}%)\n"
          f"• Status: {tr['status']}\n"
          f"• 15-Min TF: `{tr['tf_15m']}`\n"
          f"💡 {tr['action']}"
      )
      send_telegram_message(chat_id, msg_trend)
    elif text_lower in ['/nifty', '/nifty50']:
      tr = get_live_market_trend('^NSEI')
      msg_nifty = (
          '📊 *NIFTY 50*\n'
          f"• Price: `{tr['price']}` ({tr['change']}%)\n"
          f"• Bias: {tr['status']}"
      )
      send_telegram_message(chat_id, msg_nifty)
    elif text_lower in ['/banknifty']:
      tr = get_live_market_trend('^NSEBANK')
      msg_bn = (
          '🏦 *BANK NIFTY*\n'
          f"• Price: `{tr['price']}` ({tr['change']}%)\n"
          f"• Bias: {tr['status']}"
      )
      send_telegram_message(chat_id, msg_bn)
    elif text_lower in ['/sensex']:
      tr = get_live_market_trend('^BSESN')
      msg_sx = (
          '📈 *SENSEX*\n'
          f"• Price: `{tr['price']}` ({tr['change']}%)\n"
          f"• Bias: {tr['status']}"
      )
      send_telegram_message(chat_id, msg_sx)
    elif text_lower == '/pivots':
      send_telegram_message(chat_id, get_pivot_levels('^NSEI'))
    elif text_lower == '/pcr':
      p = analyze_pcr_data()
      msg_pcr = (
          '📈 *PCR*\n'
          f"• Value: `{p['pcr']}`\n"
          f"• Sentiment: {p['sentiment']}"
      )
      send_telegram_message(chat_id, msg_pcr)
    elif text_lower == '/bigmoney':
      bm = get_big_money_alert()
      msg_bm = f"🐋 *SMART MONEY*\n• {bm['action']}\n• {bm['details']}"
      send_telegram_message(chat_id, msg_bm)
    elif text_lower == '/commodity':
      send_telegram_message(
          chat_id,
          '🛢️ *MCX COMMODITY*\n• Check Crude Oil, Gold & Silver near key'
          ' support levels.',
      )
    elif text_lower == '/support':
      send_telegram_message(
          chat_id,
          '📋 *SUPPORT & ENTERPRISE REGISTRATION*\n\n• For formal business'
          ' registrations (MSME), documentation, or technical support'
          ' assistance in Bhopal, contact the administrator directly through'
          ' registered channels.\n\n_Status: Verified & Active_ ✅',
      )
    elif text_lower == '/ai_analysis':
      send_telegram_message(
          chat_id, get_ai_trading_analysis('General Market Overview')
      )
    elif text_lower == '/summary':
      send_telegram_message(chat_id, get_daily_summary())
    elif text_lower == '/signal':
      tr = get_live_market_trend('^NSEI')
      msg_sig = (
          '⚡ *SCALP SIGNAL*\n'
          f"• Price: `{tr['price']}`\n"
          f"• Mode: {tr['status']}\n"
          f"💡 {tr['action']}"
      )
      send_telegram_message(chat_id, msg_sig)
    else:
      send_telegram_message(
          chat_id,
          '✅ Command received. Use the interactive buttons below:',
          reply_markup=get_main_keyboard(),
      )

  except Exception as e:
    print(f'Webhook error: {e}')
  return 'OK', 200
        
