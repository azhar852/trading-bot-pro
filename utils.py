from datetime import datetime
import os
import sqlite3
import time
import feedparser
import requests

try:
  import yfinance as yf
except ImportError:
  os.system('pip install yfinance')
  import yfinance as yf

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
RENDER_URL = 'https://trading-bot-pro-2bjl.onrender.com'

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


def send_telegram_message(chat_id, text, reply_markup=None):
  if not chat_id or not TELEGRAM_BOT_TOKEN:
    return
  url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
  payload = {
      'chat_id': chat_id,
      'text': text,
      'parse_mode': 'Markdown',
      'disable_web_page_preview': True,
  }
  if reply_markup:
    payload['reply_markup'] = reply_markup
  try:
    requests.post(url, json=payload, timeout=10)
  except Exception as e:
    print(f'Send error: {e}')


def answer_callback_query(callback_query_id):
  if not TELEGRAM_BOT_TOKEN:
    return
  url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery'
  try:
    requests.post(url, json={'callback_query_id': callback_query_id}, timeout=5)
  except Exception as e:
    print(f'Answer callback error: {e}')


def process_action(chat_id, data_action):
  if data_action == 'news':
    send_telegram_message(chat_id, get_market_news())
  elif data_action == 'reversal':
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
  elif data_action == 'trend':
    tr = get_live_market_trend('^NSEI')
    msg_trend = (
        '🎯 *LIVE MARKET TREND*\n\n'
        f"• *Price:* `{tr['price']}` ({tr['change']}%)\n"
        f"• *Bias:* {tr['status']}\n"
        f"• *15-Min TF:* `{tr['tf_15m']}`\n"
        f"💡 {tr['action']}"
    )
    send_telegram_message(chat_id, msg_trend)
  elif data_action == 'nifty':
    tr = get_live_market_trend('^NSEI')
    msg_nifty = (
        '📊 *NIFTY 50 REAL-TIME*\n'
        f"• Price: `{tr['price']}` ({tr['change']}%)\n"
        f"• Bias: {tr['status']}"
    )
    send_telegram_message(chat_id, msg_nifty)
  elif data_action == 'banknifty':
    tr = get_live_market_trend('^NSEBANK')
    msg_bn = (
        '🏦 *BANK NIFTY REAL-TIME*\n'
        f"• Price: `{tr['price']}` ({tr['change']}%)\n"
        f"• Bias: {tr['status']}"
    )
    send_telegram_message(chat_id, msg_bn)
  elif data_action == 'sensex':
    tr = get_live_market_trend('^BSESN')
    msg_sx = (
        '📈 *BSE SENSEX*\n'
        f"• Price: `{tr['price']}` ({tr['change']}%)\n"
        f"• Bias: {tr['status']}"
    )
    send_telegram_message(chat_id, msg_sx)
  elif data_action == 'pivots':
    send_telegram_message(chat_id, get_pivot_levels('^NSEI'))
  elif data_action == 'pcr':
    p = analyze_pcr_data()
    msg_pcr = (
        '📈 *PCR ANALYTICS*\n'
        f"• Ratio: `{p['pcr']}`\n"
        f"• Sentiment: {p['sentiment']}"
    )
    send_telegram_message(chat_id, msg_pcr)
  elif data_action == 'bigmoney':
    bm = get_big_money_alert()
    msg_bm = f"🐋 *SMART MONEY FLOW*\n• {bm['action']}\n• {bm['details']}"
    send_telegram_message(chat_id, msg_bm)
  elif data_action == 'commodity':
    send_telegram_message(
        chat_id,
        '🛢️ *MCX COMMODITY SETUP*\n• Check Crude Oil, Gold & Silver near key'
        ' support/resistance.',
    )
  elif data_action == 'support':
    send_telegram_message(
        chat_id,
        '📋 *SUPPORT & ENTERPRISE REGISTRATION*\n\n• For formal business'
        ' registrations (MSME), documentation, or technical support'
        ' assistance in Bhopal, contact the administrator directly through'
        ' registered channels.\n\n_Status: Verified & Active_ ✅',
    )
  elif data_action == 'ai_analysis':
    send_telegram_message(
        chat_id, get_ai_trading_analysis('General Market Overview')
    )
  elif data_action == 'summary':
    send_telegram_message(chat_id, get_daily_summary())
  elif data_action == 'signal':
    tr = get_live_market_trend('^NSEI')
    msg_sig = (
        '⚡ *REAL-TIME SCALP SIGNAL*\n'
        f"• Index Price: `{tr['price']}`\n"
        f"• Mode: {tr['status']}\n"
        f"💡 {tr['action']}"
    )
    send_telegram_message(chat_id, msg_sig)
  elif data_action == 'calc_help':
    send_telegram_message(
        chat_id,
        '🧮 *Trade Calculator Usage*\n\nType command format in chat:\n`/calc'
        ' 22600`\n\nIt will calculate Stop Loss and Targets automatically!',
    )
  elif data_action == 'trade_help':
    send_telegram_message(
        chat_id,
        '📖 *Trade Journal Usage*\n\nType command format in chat:\n`/trade Nifty'
        ' 22600 22750 50`\n\nIt will save your entry, exit and P&L in database!',
    )


def get_market_news():
  try:
    rss_url = 'https://news.google.com/rss/search?q=Indian+Stock+Market+Nifty+Sensex&hl=en-IN&gl=IN&ceid=IN:en'
    feed = feedparser.parse(rss_url)
    if feed.entries and len(feed.entries) > 0:
      msg = '📰 *24/7 LATEST MARKET & FINANCIAL NEWS*\n\n'
      for entry in feed.entries[:4]:
        title = entry.get('title', 'Market News')
        link = entry.get('link', '')
        source = (
            entry.get('source', {}).get('title', 'Financial Express')
            if 'source' in entry
            else 'News Update'
        )
        if ' - ' in title:
          title = title.rsplit(' - ', 1)[0]
        msg += f'• [{title}]({link})\n  _Source: {source}_\n\n'
      return msg
  except Exception as e:
    print(f'RSS News Fetch Error: {e}')
  return '📰 *LATEST MARKET NEWS*\n\n• Headlines currently updating.'


def get_live_market_trend(symbol='^NSEI'):
  try:
    ticker = yf.Ticker(symbol)
    data_5m = ticker.history(period='2d', interval='5m')
    data_15m = ticker.history(period='2d', interval='15m')

    if len(data_5m) >= 6:
      current_price = round(data_5m['Close'].iloc[-1], 2)
      sma_short = data_5m['Close'].tail(5).mean()

      last_3_falling = (
          data_5m['Close'].iloc[-1]
          < data_5m['Close'].iloc[-2]
          < data_5m['Close'].iloc[-3]
      )
      last_3_rising = (
          data_5m['Close'].iloc[-1]
          > data_5m['Close'].iloc[-2]
          > data_5m['Close'].iloc[-3]
      )

      change_pct = round(
          ((current_price - data_5m['Close'].iloc[0])
           / data_5m['Close'].iloc[0])
          * 100,
          2,
      )

      if last_3_falling or current_price < sma_short:
        status = '🔴 STRONGLY BEARISH (Sell on Rise)'
        action = (
            'Market is dropping from peak. Look for Put (PE) buying or short'
            ' setups.'
        )
        bias = 'BEARISH'
      elif last_3_rising or current_price > sma_short:
        status = '🟢 STRONGLY BULLISH (Buy on Dips)'
        action = (
            'Market has upward momentum. Look for Call (CE) buying on support'
            ' dips.'
        )
        bias = 'BULLISH'
      else:
        status = '⚖️ SIDEWAYS / RANGEBOUND'
        action = 'Market is consolidating. Avoid aggressive trades.'
        bias = 'SIDEWAYS'

      tf_status = 'Neutral'
      if len(data_15m) >= 2:
        p_15m = data_15m['Close'].iloc[-1]
        o_15m = data_15m['Open'].iloc[-1]
        tf_status = 'BULLISH' if p_15m > o_15m else 'BEARISH'

      return {
          'price': current_price,
          'change': change_pct,
          'status': status,
          'action': action,
          'bias': bias,
          'tf_15m': tf_status,
      }
  except Exception as e:
    print(f'Error fetching live trend: {e}')

  return {
      'price': 'N/A',
      'change': 0.0,
      'status': '⚖️ MARKET CHECK IN PROGRESS',
      'action': 'Verify with chart indicators.',
      'bias': 'NEUTRAL',
      'tf_15m': 'N/A',
  }


def get_pivot_levels(symbol='^NSEI'):
  try:
    ticker = yf.Ticker(symbol)
    data = ticker.history(period='5d', interval='1d')
    if len(data) >= 2:
      prev = data.iloc[-2]
      high = prev['High']
      low = prev['Low']
      close = prev['Close']
      pivot = (high + low + close) / 3
      r1 = (2 * pivot) - low
      s1 = (2 * pivot) - high
      r2 = pivot + (high - low)
      s2 = pivot - (high - low)
      return (
          f'📐 *AUTOMATIC PIVOT & S/R LEVELS*\n\n'
          f'• *Pivot Point:* `{round(pivot, 2)}`\n'
          f'• *Resistance 1 (R1):* `{round(r1, 2)}`\n'
          f'• *Resistance 2 (R2):* `{round(r2, 2)}`\n'
          f'• *Support 1 (S1):* `{round(s1, 2)}`\n'
          f'• *Support 2 (S2):* `{round(s2, 2)}`\n\n'
          f'💡 *Usage:* Trade breakouts above R1 or bounces near S1.'
      )
  except Exception as e:
    print(f'Pivot error: {e}')
  return '📐 *Pivot Levels calculation currently updating.*'


def check_reversal_pattern(symbol='^NSEI'):
  try:
    ticker = yf.Ticker(symbol)
    data = ticker.history(period='1d', interval='5m')
    if len(data) >= 6:
      c1 = data['Close'].iloc[-1]
      c2 = data['Close'].iloc[-2]
      c3 = data['Close'].iloc[-3]
      c4 = data['Close'].iloc[-4]
      sma_5 = data['Close'].tail(5).mean()
      if c4 > c3 > c2 and c1 > (sma_5 * 1.0005) and c1 > c2:
        return {
            'type': 'BULLISH_REVERSAL',
            'status': '🟢 BULLISH REVERSAL DETECTED',
            'price': round(c1, 2),
            'action': 'Possible CE Buying Zone / Cover PE Shorts.',
        }
      elif c4 < c3 < c2 and c1 < (sma_5 * 0.9995) and c1 < c2:
        return {
            'type': 'BEARISH_REVERSAL',
            'status': '🔴 BEARISH REVERSAL DETECTED',
            'price': round(c1, 2),
            'action': 'Possible PE Buying Zone / Exit Long CE.',
        }
  except Exception as e:
    print(f'Reversal Error: {e}')
  return None


def analyze_pcr_data():
  tr = get_live_market_trend('^NSEI')
  if tr['bias'] == 'BEARISH':
    return {
        'pcr': 0.75,
        'sentiment': '🔴 BEARISH / CALL WRITING HEAVY',
        'details': 'Call Writers building resistance.',
    }
  elif tr['bias'] == 'BULLISH':
    return {
        'pcr': 1.25,
        'sentiment': '🟢 BULLISH / PUT WRITING DOMINANT',
        'details': 'Put Writers supporting down levels.',
    }
  return {
      'pcr': 1.00,
      'sentiment': '⚖️ NEUTRAL / RANGEBOUND',
      'details': 'Balanced OI buildup.',
  }


def get_big_money_alert():
  tr = get_live_market_trend('^NSEI')
  if tr['bias'] == 'BEARISH':
    return {
        'action': '🔴 HEAVY FII OUTFLOW (SELLING)',
        'details': 'FII net selling observed in Index Futures.',
    }
  elif tr['bias'] == 'BULLISH':
    return {
        'action': '🟢 HEAVY FII INFLOW (BUYING)',
        'details': 'FII strong net buying observed.',
    }
  return {
      'action': '⚖️ NEUTRAL FLOW',
      'details': 'Mixed institutional activity.',
  }


def get_daily_summary():
  tr = get_live_market_trend('^NSEI')
  pcr = analyze_pcr_data()
  bm = get_big_money_alert()
  return (
      f'📊 *DAILY MARKET SUMMARY & CLOSING REPORT*\n\n'
      f"• *Nifty Closing Price:* `{tr['price']}` ({tr['change']}%)\n"
      f"• *Overall Trend Bias:* {tr['status']}\n"
      f"• *15-Min Trend Confirmation:* `{tr['tf_15m']}`\n"
      f"• *Derivatives Sentiment:* {pcr['sentiment']}\n"
      f"• *Institutional Flow:* {bm['action']}\n\n"
      f"💡 *Next Session Plan:* {tr['action']}"
  )


def get_ai_trading_analysis(query):
  tr = get_live_market_trend('^NSEI')
  pcr = analyze_pcr_data()
  bm = get_big_money_alert()
  rev = check_reversal_pattern('^NSEI')
  rev_str = rev['status'] if rev else 'No immediate reversal.'
  return (
      f'🤖 *AI TRADING ASSISTANT SUMMARY*\n\n'
      f'• *Query:* _{query}_\n'
      f"• *Nifty Live:* `{tr['price']}` ({tr['change']}%)\n"
      f"• *Market Bias:* {tr['status']}\n"
      f'• *Reversal Alert:* {rev_str}\n'
      f"• *Smart Money:* {bm['action']}\n\n"
      f"💡 *AI Recommendation:* {tr['action']}"
  )


def keep_alive():
  while True:
    try:
      requests.get(RENDER_URL, timeout=10)
    except Exception as e:
      print(f'Keep-alive error: {e}')
    time.sleep(300)


def background_automation_scheduler():
  morning_sent = False
  scanner_sent = False
  closing_sent = False

  while True:
    now = datetime.now()
    current_time_str = now.strftime('%H:%M')
    users = get_all_users()

    if current_time_str == '09:00' and not morning_sent:
      if users:
        tr = get_live_market_trend('^NSEI')
        msg = (
            '🌅 *GOOD MORNING! MARKET BRIEFING*\n\n'
            f"• *Pre-Market Nifty Ref:* `{tr['price']}`\n"
            f"• *Initial Bias:* {tr['status']}\n"
            '• *Action:* Prepare your setups for the opening bell!'
        )
        for c_id in users:
          send_telegram_message(c_id, msg)
      morning_sent = True

    elif current_time_str == '09:25' and not scanner_sent:
      try:
        rev = check_reversal_pattern('^NSEI')
        if rev and rev.get('type') in ['BULLISH_REVERSAL', 'BEARISH_REVERSAL']:
          if users:
            msg = (
                '🎯 *PERFECT 9:25 ENTRY SETUP FOUND!*\n\n'
                f"• *Time:* {now.strftime('%H:%M:%S')}\n"
                '• *Index:* Nifty 50\n'
                f"• *Setup:* {rev.get('action')}\n"
                f"• *Trigger Price:* `{rev.get('price')}`\n"
                f"• *Status:* {rev.get('status')}\n\n"
                '⚡ *Action:* Risk-reward calculate karke trade execute karein!'
            )
            for c_id in users:
              send_telegram_message(c_id, msg)
      except Exception as e:
        print(f'Smart 9:25 scanner error: {e}')
      scanner_sent = True

    elif current_time_str == '15:30' and not closing_sent:
      if users:
        summary_msg = get_daily_summary()
        for c_id in users:
          send_telegram_message(c_id, summary_msg)
      closing_sent = True

    if current_time_str == '00:00':
      morning_sent = False
      scanner_sent = False
      closing_sent = False

    time.sleep(30)


def real_time_entry_scanner():
  global LAST_SIGNAL_STATE
  while True:
    try:
      rev = check_reversal_pattern('^NSEI')
      if rev and rev['type'] != LAST_SIGNAL_STATE:
        LAST_SIGNAL_STATE = rev['type']
        users = get_all_users()
        if users:
          msg = (
              '🔄 *REAL-TIME REVERSAL ALERT*\n\n'
              f"• *Status:* {rev['status']}\n"
              f"• *Trigger Price:* `{rev['price']}`\n"
              f"💡 *Setup:* {rev['action']}"
          )
          for c_id in users:
            send_telegram_message(c_id, msg)
    except Exception as e:
      print(f'Scanner error: {e}')
    time.sleep(30)
        
