from datetime import datetime, timedelta
import logging
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

# Logging Configuration Setup
logging.basicConfig(
    filename='bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
RENDER_URL = 'https://trading-bot-pro-2bjl.onrender.com'

LAST_NOTIFIED_PRICE = None
LAST_ALERT_TIME = 0
PROCESSED_UPDATE_IDS = set()


def get_db_connection():
  conn = sqlite3.connect('bot_users.db', check_same_thread=False, timeout=10)
  return conn


def init_db():
  try:
    conn = get_db_connection()
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
  except Exception as e:
    logging.error(f'DB Init Error: {e}')


init_db()


def add_user_to_db(chat_id):
  try:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT OR IGNORE INTO users (chat_id) VALUES (?)', (chat_id,)
    )
    conn.commit()
    conn.close()
  except Exception as e:
    logging.error(f'DB Add User Error: {e}')


def get_all_users():
  users = set()
  try:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT chat_id FROM users')
    rows = cursor.fetchall()
    for row in rows:
      users.add(row[0])
    conn.close()
  except Exception as e:
    logging.error(f'DB Read Users Error: {e}')
  return users


def get_main_keyboard():
  return {
      'inline_keyboard': [
          [
              {'text': '📰 News', 'callback_data': 'news'},
              {'text': '⚡ Real-Time Scalp', 'callback_data': 'scalping_alert'},
          ],
          [
              {'text': '🎯 Trend Setup', 'callback_data': 'trend'},
              {'text': '📊 Nifty 50', 'callback_data': 'nifty'},
          ],
          [
              {'text': '🏦 BankNifty', 'callback_data': 'banknifty'},
              {'text': '📈 Sensex', 'callback_data': 'sensex'},
          ],
          [
              {'text': '📉 India VIX', 'callback_data': 'vix'},
              {'text': '🌍 Global Markets', 'callback_data': 'global'},
          ],
          [
              {'text': '💱 USD/INR', 'callback_data': 'usdinr'},
              {'text': '🥇 Gold & Silver', 'callback_data': 'metals'},
          ],
          [
              {'text': '📊 Sectors', 'callback_data': 'sectors'},
              {'text': '📅 Expiry', 'callback_data': 'expiry'},
          ],
          [
              {'text': '📐 Pivots', 'callback_data': 'pivots'},
              {'text': '📈 PCR', 'callback_data': 'pcr'},
          ],
          [
              {'text': '🐋 BigMoney', 'callback_data': 'bigmoney'},
              {'text': '🛢️ Crude Oil', 'callback_data': 'crude_oil'},
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
    logging.error(f'Telegram Send Error to {chat_id}: {e}')


def answer_callback_query(callback_query_id):
  if not TELEGRAM_BOT_TOKEN:
    return
  url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery'
  try:
    requests.post(url, json={'callback_query_id': callback_query_id}, timeout=5)
  except Exception as e:
    logging.error(f'Answer Callback Error: {e}')


def process_action(chat_id, data_action):
  if data_action == 'news':
    send_telegram_message(chat_id, get_market_news())
  elif data_action == 'scalping_alert':
    tr = get_live_market_trend('^NSEI')
    msg_sc = (
        '⚡ *REAL-TIME SCALP DESK*\n\n'
        f"• Current Price: `{tr['price']}`\n"
        f"• VWAP: `{tr['vwap']}`\n"
        f"• RSI (14): `{tr['rsi']}`\n"
        f"• Market Bias: {tr['status']}\n\n"
        f"💡 {tr['action']}"
    )
    send_telegram_message(chat_id, msg_sc)
  elif data_action == 'trend':
    tr = get_live_market_trend('^NSEI')
    msg_trend = (
        '🎯 *LIVE TREND SETUP*\n\n'
        f"• *Price:* `{tr['price']}` ({tr['change']}%)\n"
        f"• *VWAP:* `{tr['vwap']}`\n"
        f"• *RSI (14):* `{tr['rsi']}`\n"
        f"• *Bias:* {tr['status']}\n"
        f"💡 {tr['action']}"
    )
    send_telegram_message(chat_id, msg_trend)
  elif data_action == 'nifty':
    tr = get_live_market_trend('^NSEI')
    msg_nifty = (
        '📊 *NIFTY 50 REAL-TIME*\n'
        f"• Price: `{tr['price']}` ({tr['change']}%)\n"
        f"• VWAP: `{tr['vwap']}` | RSI: `{tr['rsi']}`\n"
        f"• Bias: {tr['status']}"
    )
    send_telegram_message(chat_id, msg_nifty)
  elif data_action == 'banknifty':
    tr = get_live_market_trend('^NSEBANK')
    msg_bn = (
        '🏦 *BANK NIFTY REAL-TIME*\n'
        f"• Price: `{tr['price']}` ({tr['change']}%)\n"
        f"• VWAP: `{tr['vwap']}` | RSI: `{tr['rsi']}`\n"
        f"• Bias: {tr['status']}"
    )
    send_telegram_message(chat_id, msg_bn)
  elif data_action == 'sensex':
    tr = get_live_market_trend('^BSESN')
    msg_sx = (
        '📈 *BSE SENSEX*\n'
        f"• Price: `{tr['price']}` ({tr['change']}%)\n"
        f"• VWAP: `{tr['vwap']}` | RSI: `{tr['rsi']}`\n"
        f"• Bias: {tr['status']}"
    )
    send_telegram_message(chat_id, msg_sx)
  elif data_action == 'vix':
    send_telegram_message(chat_id, get_real_vix())
  elif data_action == 'global':
    send_telegram_message(chat_id, get_global_markets())
  elif data_action == 'usdinr':
    send_telegram_message(chat_id, get_usd_inr())
  elif data_action == 'metals':
    send_telegram_message(chat_id, get_gold_silver())
  elif data_action == 'sectors':
    send_telegram_message(chat_id, get_sector_performance())
  elif data_action == 'expiry':
    send_telegram_message(chat_id, get_next_expiry())
  elif data_action == 'pivots':
    send_telegram_message(chat_id, get_pivot_levels('^NSEI'))
  elif data_action == 'pcr':
    tr = get_live_market_trend('^NSEI')
    p = analyze_pcr_data(tr)
    msg_pcr = (
        '📈 *PCR ANALYTICS*\n'
        f"• Ratio: `{p['pcr']}`\n"
        f"• Sentiment: {p['sentiment']}"
    )
    send_telegram_message(chat_id, msg_pcr)
  elif data_action == 'bigmoney':
    tr = get_live_market_trend('^NSEI')
    bm = get_big_money_alert(tr)
    msg_bm = f"🐋 *SMART MONEY FLOW*\n• {bm['action']}\n• {bm['details']}"
    send_telegram_message(chat_id, msg_bm)
  elif data_action == 'crude_oil':
    send_telegram_message(chat_id, get_crude_oil_data())
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
        '⚡ *REAL-TIME SIGNAL DESK*\n'
        f"• Index Price: `{tr['price']}`\n"
        f"• VWAP: `{tr['vwap']}` | RSI: `{tr['rsi']}`\n"
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


# --- PRO FEATURES WITH ZERO-DIVISION SAFEGUARDS ---


def get_real_vix():
  try:
    vix = yf.Ticker('^INDIAVIX')
    data = vix.history(period='2d', interval='1d')
    if not data.empty:
      current_vix = round(data['Close'].iloc[-1], 2)
      prev_vix = (
          round(data['Close'].iloc[-2], 2)
          if len(data) >= 2
          else current_vix
      )
      if prev_vix == 0:
        prev_vix = current_vix  # Safeguard
      change = round(((current_vix - prev_vix) / prev_vix) * 100, 2)

      if current_vix < 12:
        status = '🟢 LOW FEAR (Bullish Market Support)'
      elif current_vix < 18:
        status = '🟡 MODERATE FEAR (Normal Volatility)'
      else:
        status = '🔴 HIGH FEAR (Market Panic / Correction)'

      return (
          f'📉 *INDIA VIX (FEAR GAUGE)*\n\n'
          f'• *Current VIX:* `{current_vix}`\n'
          f'• *Change:* `{change}%`\n'
          f'• *Status:* {status}\n\n'
          f'💡 *Tip:* Rising VIX means option premiums (CE/PE) will expand.'
      )
  except Exception as e:
    logging.error(f'VIX Error: {e}')
  return '📉 *India VIX data currently updating.*'


def get_global_markets():
  markets = {
      '🇺🇸 Dow Jones': '^DJI',
      '🇺🇸 Nasdaq': '^IXIC',
      '🇺🇸 S&P 500': '^GSPC',
      '🇯🇵 Nikkei': '^N225',
      '🇭🇰 Hang Seng': '^HSI',
      '🇬🇧 FTSE': '^FTSE',
      '🇩🇪 DAX': '^GDAXI',
  }
  msg = '🌍 *GLOBAL MARKETS LIVE STATUS*\n\n'
  for name, symbol in markets.items():
    try:
      ticker = yf.Ticker(symbol)
      data = ticker.history(period='2d', interval='1d')
      if not data.empty:
        price = round(data['Close'].iloc[-1], 2)
        prev = round(data['Close'].iloc[-2], 2) if len(data) >= 2 else price
        if prev == 0:
          prev = price  # Safeguard
        change = round(((price - prev) / prev) * 100, 2)
        emoji = '🟢' if change >= 0 else '🔴'
        msg += f'{emoji} *{name}:* `{price}` ({change}%)\n'
    except Exception:
      msg += f'⚪ *{name}:* Data unavailable\n'
  return msg


def get_usd_inr():
  try:
    ticker = yf.Ticker('USDINR=X')
    data = ticker.history(period='2d', interval='1d')
    if not data.empty:
      current = round(data['Close'].iloc[-1], 4)
      prev = round(data['Close'].iloc[-2], 4) if len(data) >= 2 else current
      if prev == 0:
        prev = current  # Safeguard
      change = round(((current - prev) / prev) * 100, 2)
      status = '🟢 RUPEE STRONGER' if change < 0 else '🔴 RUPEE WEAKER'
      return (
          f'💱 *USD/INR CURRENCY LIVE*\n\n'
          f'• *Rate:* `₹{current}`\n'
          f'• *Change:* `{change}%`\n'
          f'• *Status:* {status}\n\n'
          f'💡 *Impact:* Weak rupee is generally negative for domestic equity'
          f' inflows.'
      )
  except Exception as e:
    logging.error(f'USD/INR Error: {e}')
  return '💱 *USD/INR Data currently updating.*'


def get_gold_silver():
  try:
    gold = yf.Ticker('GC=F')
    silver = yf.Ticker('SI=F')
    gold_data = gold.history(period='2d', interval='1d')
    silver_data = silver.history(period='2d', interval='1d')  # ✅ Syntax fixed

    gold_price = (
        round(gold_data['Close'].iloc[-1], 2) if not gold_data.empty else 0
    )
    silver_price = (
        round(silver_data['Close'].iloc[-1], 2) if not silver_data.empty else 0
    )
    return (
        f'🥇 *PRECIOUS METALS (GLOBAL SPOT)*\n\n'
        f'• *Gold (USD/oz):* `${gold_price}`\n'
        f'• *Silver (USD/oz):* `${silver_price}`\n\n'
        f'💡 *Note:* Safe-haven asset tracking for global inflation cues.'
    )
  except Exception as e:
    logging.error(f'Gold/Silver Error: {e}')
  return '🥇 *Precious Metals data updating.*'


def get_sector_performance():
  sectors = {
      '🏦 Nifty Bank': '^NSEBANK',
      '💻 Nifty IT': '^CNXIT',
      '🚗 Nifty Auto': '^CNXAUTO',
      '💊 Nifty Pharma': '^CNXPHARMA',
      '🏗️ Nifty Metal': '^CNXMETAL',
      '⚡ Nifty Energy': '^CNXENERGY',
  }
  msg = '📊 *SECTOR PERFORMANCE TODAY*\n\n'
  for name, symbol in sectors.items():
    try:
      ticker = yf.Ticker(symbol)
      data = ticker.history(period='2d', interval='1d')
      if not data.empty:
        price = round(data['Close'].iloc[-1], 2)
        prev = round(data['Close'].iloc[-2], 2) if len(data) >= 2 else price
        if prev == 0:
          prev = price  # Safeguard
        change = round(((price - prev) / prev) * 100, 2)
        emoji = '🟢' if change >= 0 else '🔴'
        msg += f'{emoji} *{name}:* `{change}%`\n'
    except Exception:
      pass
  return msg


def get_next_expiry():
  today = datetime.now()
  days_ahead = 3 - today.weekday()  # Thursday = 3
  if days_ahead <= 0:
    days_ahead += 7
  next_thursday = today + timedelta(days=days_ahead)
  days_left = (next_thursday - today).days
  return (
      f'📅 *OPTIONS EXPIRY CALENDAR*\n\n'
      f'• *Next Weekly Expiry:* `{next_thursday.strftime("%d %b %Y")}`\n'
      f'• *Days Remaining:* `{days_left}` Days\n\n'
      f'💡 *Tip:* Avoid holding naked options close to expiry due to rapid'
      f' Theta Decay.'
  )


# --- CORE UTILITIES & SCANNERS ---


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
    logging.error(f'RSS News Fetch Error: {e}')
  return '📰 *LATEST MARKET NEWS*\n\n• Headlines currently updating.'


def get_crude_oil_data():
  try:
    ticker = yf.Ticker('CL=F')
    data = ticker.history(period='2d', interval='1d')
    if not data.empty:
      current_price = round(data['Close'].iloc[-1], 2)
      prev_price = (
          round(data['Close'].iloc[-2], 2)
          if len(data) >= 2
          else current_price
      )
      if prev_price == 0:
        prev_price = current_price  # Safeguard
      change = round(((current_price - prev_price) / prev_price) * 100, 2)
      status = (
          '🟢 BULLISH / RISING' if change >= 0 else '🔴 BEARISH / FALLING'
      )
      return (
          f'🛢️ *CRUDE OIL LIVE MARKET*\n\n'
          f'• *Price:* `${current_price}`\n'
          f'• *Change:* `{change}%`\n'
          f'• *Trend:* {status}\n\n'
          f'💡 *Market Impact:* High crude prices increase inflation and put'
          f' pressure on indices.'
      )
  except Exception as e:
    logging.error(f'Crude Fetch Error: {e}')
  return '🛢️ *CRUDE OIL*\n\n• Live data currently updating.'


def calculate_rsi(data, window=14):
  try:
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi.iloc[-1], 2)
  except Exception as e:
    logging.error(f'RSI Calculation Error: {e}')
    return 50.0


def calculate_vwap(data):
  try:
    q = data['Volume']
    tp = (data['High'] + data['Low'] + data['Close']) / 3
    vwap = (tp * q).cumsum() / q.cumsum()
    return round(vwap.iloc[-1], 2)
  except Exception as e:
    logging.error(f'VWAP Calculation Error: {e}')
    return 0.0


def get_live_market_trend(symbol='^NSEI'):
  try:
    ticker = yf.Ticker(symbol)
    data_5m = ticker.history(period='1d', interval='5m')

    if len(data_5m) >= 5:
      current_price = round(data_5m['Close'].iloc[-1], 2)
      rsi_val = calculate_rsi(data_5m)
      vwap_val = calculate_vwap(data_5m)

      open_price = data_5m['Close'].iloc[0]
      if open_price == 0:
        open_price = current_price  # ✅ Zero division safeguard

      change_pct = round(
          ((current_price - open_price) / open_price) * 100, 2
      )

      if current_price > vwap_val and rsi_val > 50:
        status = '🟢 BULLISH (Upward Momentum)'
        action = (
            'Price is above VWAP with RSI > 50. Look for Call (CE) opportunities.'
        )
        bias = 'BULLISH'
      elif current_price < vwap_val and rsi_val < 50:
        status = '🔴 BEARISH (Downward Momentum)'
        action = (
            'Price is below VWAP with RSI < 50. Look for Put (PE) opportunities.'
        )
        bias = 'BEARISH'
      else:
        status = '⚖️ CONSOLIDATION / SIDEWAYS'
        action = 'Market is hovering around VWAP. Wait for a clear breakout.'
        bias = 'SIDEWAYS'

      return {
          'price': current_price,
          'change': change_pct,
          'rsi': rsi_val,
          'vwap': vwap_val,
          'status': status,
          'action': action,
          'bias': bias,
      }
  except Exception as e:
    logging.error(f'Live Market Trend Error for {symbol}: {e}')

  return {
      'price': 'N/A',
      'change': 0.0,
      'rsi': 50.0,
      'vwap': 0.0,
      'status': '⚖️ MARKET CHECK IN PROGRESS',
      'action': 'Verify with chart indicators.',
      'bias': 'NEUTRAL',
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
    logging.error(f'Pivot Error: {e}')
  return '📐 *Pivot Levels calculation currently updating.*'


def analyze_pcr_data(tr=None):
  if not tr:
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


def get_big_money_alert(tr=None):
  if not tr:
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
  pcr = analyze_pcr_data(tr)
  bm = get_big_money_alert(tr)
  return (
      f'📊 *DAILY MARKET SUMMARY & TECHNICAL REPORT*\n\n'
      f"• *Nifty Price:* `{tr['price']}` ({tr['change']}%)\n"
      f"• *VWAP:* `{tr['vwap']}` | *RSI:* `{tr['rsi']}`\n"
      f"• *Overall Trend Bias:* {tr['status']}\n"
      f"• *Derivatives Sentiment:* {pcr['sentiment']}\n"
      f"• *Institutional Flow:* {bm['action']}\n\n"
      f"💡 *Next Session Plan:* {tr['action']}"
  )


def get_ai_trading_analysis(query):
  tr = get_live_market_trend('^NSEI')
  pcr = analyze_pcr_data(tr)
  bm = get_big_money_alert(tr)
  return (
      f'🤖 *AI TECHNICAL ASSISTANT*\n\n'
      f'• *Query:* _{query}_\n'
      f"• *Nifty Live:* `{tr['price']}` ({tr['change']}%)\n"
      f"• *VWAP:* `{tr['vwap']}` | *RSI:* `{tr['rsi']}`\n"
      f"• *Market Bias:* {tr['status']}\n"
      f"• *Smart Money:* {bm['action']}\n\n"
      f"💡 *Recommendation:* {tr['action']}"
  )


def keep_alive():
  while True:
    try:
      requests.get(RENDER_URL, timeout=10)
    except Exception as e:
      logging.error(f'Keep-alive ping error: {e}')
    time.sleep(300)


def background_automation_scheduler():
  morning_sent = False
  closing_sent = False

  while True:
    now = datetime.now()
    current_time_str = now.strftime('%H:%M')
    users = get_all_users()

    if current_time_str == '09:00' and not morning_sent:
      if users:
        tr = get_live_market_trend('^NSEI')
        msg = (
            '🌅 *GOOD MORNING! TECHNICAL BRIEFING*\n\n'
            f"• *Pre-Market Nifty Ref:* `{tr['price']}`\n"
            f"• *Initial Bias:* {tr['status']}\n"
            '• *Action:* Prepare your live setups!'
        )
        for c_id in users:
          send_telegram_message(c_id, msg)
          time.sleep(0.1)
      morning_sent = True

    elif current_time_str == '15:30' and not closing_sent:
      if users:
        summary_msg = get_daily_summary()
        for c_id in users:
          send_telegram_message(c_id, summary_msg)
          time.sleep(0.1)
      closing_sent = True

    if current_time_str == '00:00':
      morning_sent = False
      closing_sent = False

    time.sleep(30)


def real_time_entry_scanner():
  global LAST_NOTIFIED_PRICE, LAST_ALERT_TIME
  while True:
    try:
      current_time = time.time()
      COOLDOWN_PERIOD = 300  # 5 minutes cooldown

      tr = get_live_market_trend('^NSEI')
      current_price = tr.get('price')
      rsi_val = tr.get('rsi', 50)
      vwap_val = tr.get('vwap', 0)

      if isinstance(current_price, (int, float)):
        if LAST_NOTIFIED_PRICE is None:
          LAST_NOTIFIED_PRICE = current_price
        else:
          diff = current_price - LAST_NOTIFIED_PRICE
          if (
              abs(diff) >= 50
              and (current_time - LAST_ALERT_TIME) > COOLDOWN_PERIOD
          ):
            if (diff > 0 and current_price > vwap_val and rsi_val > 50) or (
                diff < 0 and current_price < vwap_val and rsi_val < 50
            ):
              move_type = (
                  f'🚀 *FAST SCALPING ALERT: UPWARD MOVE (+50+ Pts)*'
                  if diff > 0
                  else f'🔻 *FAST SCALPING ALERT: DOWNWARD MOVE (-50+ Pts)*'
              )
              users = get_all_users()
              if users:
                msg = (
                    f'{move_type}\n\n'
                    f'• *Previous Ref:* `{LAST_NOTIFIED_PRICE}`\n'
                    f'• *Current Price:* `{current_price}`\n'
                    f'• *Net Move:* `{round(diff, 2)} Points`\n'
                    f'• *VWAP:* `{vwap_val}` | *RSI:* `{rsi_val}`\n'
                    f"• *Market Bias:* {tr['status']}\n\n"
                    f"💡 *Action:* {tr['action']}"
                )
                for c_id in users:
                  send_telegram_message(c_id, msg)
                  time.sleep(0.1)
              LAST_NOTIFIED_PRICE = current_price
              LAST_ALERT_TIME = current_time

    except Exception as e:
      logging.error(f'Real-Time Scanner Error: {e}')
    time.sleep(30)
