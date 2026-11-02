import logging
import os
import threading
from flask import Flask, request
from utils import (
    PROCESSED_UPDATE_IDS,
    add_user_to_db,
    analyze_pcr_data,
    answer_callback_query,
    background_automation_scheduler,
    get_ai_trading_analysis,
    get_big_money_alert,
    get_daily_summary,
    get_db_connection,
    get_global_markets,
    get_gold_silver,
    get_live_market_trend,
    get_main_keyboard,
    get_market_news,
    get_next_expiry,
    get_pivot_levels,
    get_real_vix,
    get_sector_performance,
    get_usd_inr,
    keep_alive,
    process_action,
    real_time_entry_scanner,
    send_telegram_message,
)

app = Flask(__name__)

# Logging setup for app.py
logging.basicConfig(
    filename='bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)


@app.route('/')
def home():
  return 'MyMarketAlertBot Ultimate Pro Webhook Active!'


@app.route('/webhook', methods=['POST'])
def telegram_webhook():
  try:
    update = request.get_json(force=True, silent=True)
    if not update:
      return 'OK', 200

    logging.info(f'📥 Received Update ID: {update.get("update_id")}')

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

    if 'callback_query' in update:
      cq = update['callback_query']
      answer_callback_query(cq['id'])
      data_action = cq['data']
      process_action(chat_id, data_action)
      return 'OK', 200

    message = update.get('message', {})
    text = message.get('text', '').strip()
    text_lower = text.lower()

    if chat_id:
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
          if len(parts) < 2:
            raise IndexError
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
        except IndexError:
          send_telegram_message(
              chat_id, '⚠️ Sahi format use karein: `/calc 22600`'
          )
        except ValueError:
          send_telegram_message(
              chat_id,
              '⚠️ Kripya sirf numbers ka upyog karein (e.g., `/calc 22600`)',
          )
        except Exception:
          send_telegram_message(
              chat_id, '⚠️ Kuchh galat ho gaya. Dobara try karein.'
          )

      elif text_lower.startswith('/trade'):
        try:
          parts = text.split()
          if len(parts) < 5:
            raise IndexError
          symbol = parts[1]
          entry = float(parts[2])
          exit_p = float(parts[3])
          qty = int(parts[4])
          pnl = (exit_p - entry) * qty

          conn = get_db_connection()
          cursor = conn.cursor()
          cursor.execute(
              'INSERT INTO trades (chat_id, symbol, entry_price, exit_price,'
              ' qty, pnl, date) VALUES (?, ?, ?, ?, ?, ?, datetime("now"))',
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
        except IndexError:
          send_telegram_message(
              chat_id, '⚠️ Format: `/trade Nifty 22600 22750 50`'
          )
        except ValueError:
          send_telegram_message(
              chat_id,
              '⚠️ Entry, Exit aur Qty mein sirf numbers hone chahiye.',
          )
        except Exception:
          send_telegram_message(chat_id, '⚠️ Trade save karne mein error aaya.')

      elif text_lower in ['/vix', '/india_vix']:
        send_telegram_message(chat_id, get_real_vix())
      elif text_lower in ['/global', '/world']:
        send_telegram_message(chat_id, get_global_markets())
      elif text_lower in ['/usdinr', '/dollar']:
        send_telegram_message(chat_id, get_usd_inr())
      elif text_lower in ['/metals', '/gold']:
        send_telegram_message(chat_id, get_gold_silver())
      elif text_lower in ['/sectors', '/sector']:
        send_telegram_message(chat_id, get_sector_performance())
      elif text_lower in ['/expiry', '/expiration']:
        send_telegram_message(chat_id, get_next_expiry())

      elif text_lower == '/ai_analysis':
        send_telegram_message(
            chat_id, get_ai_trading_analysis('General Market Overview')
        )
      elif text_lower == '/ai' or text_lower.startswith('/ai '):
        query = text[3:].strip() or 'Overall market condition'
        send_telegram_message(chat_id, get_ai_trading_analysis(query))
      elif text_lower in ['/trend', '/market']:
        tr = get_live_market_trend('^NSEI')
        msg_trend = (
            '🎯 *LIVE TREND (NIFTY)*\n'
            f"• Price: `{tr['price']}` ({tr['change']}%)\n"
            f"• Status: {tr['status']}\n"
            f"• VWAP: `{tr['vwap']}` | RSI: `{tr['rsi']}`\n"
            f"💡 {tr['action']}"
        )
        send_telegram_message(chat_id, msg_trend)
      elif text_lower in ['/nifty', '/nifty50']:
        tr = get_live_market_trend('^NSEI')
        msg_nifty = (
            '📊 *NIFTY 50*\n'
            f"• Price: `{tr['price']}` ({tr['change']}%)\n"
            f"• VWAP: `{tr['vwap']}` | RSI: `{tr['rsi']}`\n"
            f"• Bias: {tr['status']}"
        )
        send_telegram_message(chat_id, msg_nifty)
      elif text_lower in ['/banknifty']:
        tr = get_live_market_trend('^NSEBANK')
        msg_bn = (
            '🏦 *BANK NIFTY*\n'
            f"• Price: `{tr['price']}` ({tr['change']}%)\n"
            f"• VWAP: `{tr['vwap']}` | RSI: `{tr['rsi']}`\n"
            f"• Bias: {tr['status']}"
        )
        send_telegram_message(chat_id, msg_bn)
      elif text_lower in ['/sensex']:
        tr = get_live_market_trend('^BSESN')
        msg_sx = (
            '📈 *SENSEX*\n'
            f"• Price: `{tr['price']}` ({tr['change']}%)\n"
            f"• VWAP: `{tr['vwap']}` | RSI: `{tr['rsi']}`\n"
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
      elif text_lower == '/summary':
        send_telegram_message(chat_id, get_daily_summary())
      elif text_lower == '/signal':
        tr = get_live_market_trend('^NSEI')
        msg_sig = (
            '⚡ *SCALP SIGNAL*\n'
            f"• Price: `{tr['price']}`\n"
            f"• VWAP: `{tr['vwap']}` | RSI: `{tr['rsi']}`\n"
            f"• Mode: {tr['status']}\n"
            f"💡 {tr['action']}"
        )
        send_telegram_message(chat_id, msg_sig)
      elif text_lower == '/news':
        send_telegram_message(chat_id, get_market_news())
      elif text_lower == '/reversal':
        tr = get_live_market_trend('^NSEI')
        msg_rev = (
            '🔄 *MARKET TREND & REVERSAL STATUS*\n'
            f"• Status: {tr['status']}\n"
            f"• Price: `{tr['price']}`\n"
            f"• VWAP: `{tr['vwap']}` | RSI: `{tr['rsi']}`\n"
            f"💡 {tr['action']}"
        )
        send_telegram_message(chat_id, msg_rev)
      else:
        send_telegram_message(
            chat_id,
            '✅ Command received. Use the interactive buttons below:',
            reply_markup=get_main_keyboard(),
        )

  except Exception as e:
    logging.error(f'❌ Webhook error: {e}')
  return 'OK', 200


# Start Background Threads
threading.Thread(target=keep_alive, daemon=True).start()
threading.Thread(target=background_automation_scheduler, daemon=True).start()
threading.Thread(target=real_time_entry_scanner, daemon=True).start()

if __name__ == '__main__':
  port = int(os.environ.get('PORT', 10000))
  app.run(host='0.0.0.0', port=port)
    
