import httpx
import sqlite3
import asyncio
import logging
from datetime import datetime

# ==================== ØªÙ†Ø¸ÛŒÙ…Ø§Øª ====================
TOKEN = "8600298019:AAGuH6U-BKB3O30LbJAOubB4A01Yy8_TDMI"
OWNER_ID = 1374081605
RESERVE_CHANNEL = -1003764301938
REQUIRED_CHANNELS = ["@Nebulastars", "@Nebulastarsgp"]
BOT_USERNAME = "Nebularefbot"
STARS_PER_REFERRAL = 3
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

# ==================== Ø§ÛŒÙ…ÙˆØ¬ÛŒ Ù¾Ø±ÛŒÙ…ÛŒÙˆÙ… ====================
def pe(emoji_id, fallback="â­"):
    return f"<tg-emoji emoji-id='{emoji_id}'>{fallback}</tg-emoji>"

EMOJI = {
    "stars":    pe("5803311247159988988", "â­"),
    "account":  pe("5875255350982087963", "ðŸ‘¤"),
    "support":  pe("5803311247159988988", "ðŸŽ§"),
    "welcome1": pe("5893189613991759811", "ðŸ’¥"),
    "welcome2": pe("5809695698865623554", "ðŸŒŸ"),
    "arrow":    pe("5803120932864136855", "ðŸ‘‡"),
    "name":     pe("5217822164362739968", "ðŸ‘‘"),
    "id":       pe("5422439311196834318", "ðŸ’¡"),
    "username": pe("5424972470023104089", "ðŸ”¥"),
    "invites":  pe("5415655814079723871", "ðŸ”"),
    "starz":    pe("5325547803936572038", "âœ¨"),
    "owner":    pe("5438496463044752972", "â­"),
    "back":     pe("5416041192905265756", "ðŸ”™"),
    "acctitle": pe("5461117441612462242", "ðŸ˜Š"),
    "referral": pe("5305265301917549162", "ðŸ”—"),
    "globe":    pe("5447410659077661506", "ðŸŒ"),
    "linkarrow":pe("5803120932864136855", "ðŸ‘‡"),
}


# ==================== Ø¯ÛŒØªØ§Ø¨ÛŒØ³ ====================
def init_db():
    conn = sqlite3.connect("nebula.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT,
        referral_count INTEGER DEFAULT 0, stars INTEGER DEFAULT 0,
        referred_by INTEGER, joined_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER, referred_id INTEGER, joined_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS star_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, post_link TEXT, status TEXT DEFAULT 'pending', created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, message TEXT, status TEXT DEFAULT 'open', created_at TEXT)""")
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect("nebula.db")
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def add_user(user_id, username, full_name, referred_by=None):
    conn = sqlite3.connect("nebula.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, full_name, referred_by, joined_at) VALUES (?,?,?,?,?)",
              (user_id, username, full_name, referred_by, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def add_referral(referrer_id, referred_id):
    conn = sqlite3.connect("nebula.db")
    c = conn.cursor()
    c.execute("SELECT id FROM referrals WHERE referred_id = ?", (referred_id,))
    if c.fetchone():
        conn.close()
        return False
    c.execute("INSERT INTO referrals (referrer_id, referred_id, joined_at) VALUES (?,?,?)",
              (referrer_id, referred_id, datetime.now().isoformat()))
    c.execute("UPDATE users SET referral_count = referral_count + 1 WHERE user_id = ?", (referrer_id,))
    c.execute("SELECT referral_count FROM users WHERE user_id = ?", (referrer_id,))
    row = c.fetchone()
    got_star = False
    if row and row[0] % STARS_PER_REFERRAL == 0:
        c.execute("UPDATE users SET stars = stars + 1 WHERE user_id = ?", (referrer_id,))
        got_star = True
    conn.commit()
    conn.close()
    return got_star

def add_star_request(user_id, post_link):
    conn = sqlite3.connect("nebula.db")
    c = conn.cursor()
    c.execute("INSERT INTO star_requests (user_id, post_link, created_at) VALUES (?,?,?)",
              (user_id, post_link, datetime.now().isoformat()))
    req_id = c.lastrowid
    conn.commit()
    conn.close()
    return req_id

def add_ticket(user_id, message):
    conn = sqlite3.connect("nebula.db")
    c = conn.cursor()
    c.execute("INSERT INTO tickets (user_id, message, created_at) VALUES (?,?,?)",
              (user_id, message, datetime.now().isoformat()))
    ticket_id = c.lastrowid
    conn.commit()
    conn.close()
    return ticket_id

def done_request(user_id, req_id):
    conn = sqlite3.connect("nebula.db")
    c = conn.cursor()
    c.execute("UPDATE users SET stars = stars - 1 WHERE user_id = ? AND stars > 0", (user_id,))
    c.execute("UPDATE star_requests SET status = 'done' WHERE id = ?", (req_id,))
    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect("nebula.db")
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM referrals")
    total_referrals = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM star_requests WHERE status = 'pending'")
    pending = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM tickets WHERE status = 'open'")
    tickets = c.fetchone()[0]
    conn.close()
    return total_users, total_referrals, pending, tickets

# ==================== API ØªÙ„Ú¯Ø±Ø§Ù… ====================
async def api(method, **kwargs):
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{BASE_URL}/{method}", json=kwargs, timeout=30)
        return r.json()

async def send_message(chat_id, text, reply_markup=None, parse_mode="HTML"):
    params = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_markup:
        params["reply_markup"] = reply_markup
    return await api("sendMessage", **params)

async def edit_message(chat_id, message_id, text, reply_markup=None, parse_mode="HTML"):
    params = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": parse_mode}
    if reply_markup:
        params["reply_markup"] = reply_markup
    return await api("editMessageText", **params)

async def answer_callback(callback_id, text=""):
    await api("answerCallbackQuery", callback_query_id=callback_id, text=text)

async def check_membership(user_id):
    for ch in REQUIRED_CHANNELS:
        r = await api("getChatMember", chat_id=ch, user_id=user_id)
        if not r.get("ok") or r["result"]["status"] in ["left", "kicked", "banned"]:
            return False
    return True

# ==================== Ú©ÛŒØ¨ÙˆØ±Ø¯Ù‡Ø§ ====================
def main_menu():
    return {
        "inline_keyboard": [[
            {"text": "Ø§Ø³ØªØ§Ø±Ø²", "callback_data": "stars", "icon_custom_emoji_id": "5803311247159988988"},
            {"text": "Ø±ÙØ±Ø§Ù„", "callback_data": "referral", "icon_custom_emoji_id": "5305265301917549162"}
        ], [
            {"text": "Ø­Ø³Ø§Ø¨ Ú©Ø§Ø±Ø¨Ø±ÛŒ", "callback_data": "account", "icon_custom_emoji_id": "5875255350982087963"},
            {"text": "Ù¾Ø´ØªÛŒØ¨Ø§Ù†ÛŒ", "callback_data": "support", "icon_custom_emoji_id": "5803311247159988988"}
        ]]
    }

def join_keyboard():
    buttons = []
    for ch in REQUIRED_CHANNELS:
        buttons.append([{"text": f"Ø¹Ø¶ÙˆÛŒØª Ø¯Ø± {ch}", "url": f"https://t.me/{ch[1:]}"}])
    buttons.append([{"text": "âœ… Ø¹Ø¶Ùˆ Ø´Ø¯Ù…", "callback_data": "check_join"}])
    return {"inline_keyboard": buttons}

def back_button(cb="back_main"):
    return {"inline_keyboard": [[
        {"text": "Ø¨Ø§Ø²Ú¯Ø´Øª", "callback_data": cb, "icon_custom_emoji_id": "5416041192905265756"}
    ]]}

def stars_keyboard():
    return {"inline_keyboard": [
        [{"text": "Ø¯Ø±ÛŒØ§ÙØª Ø§Ø³ØªØ§Ø±Ø²", "callback_data": "claim_star", "icon_custom_emoji_id": "5325547803936572038"}],
        [{"text": "Ø¨Ø§Ø²Ú¯Ø´Øª", "callback_data": "back_main", "icon_custom_emoji_id": "5416041192905265756"}]
    ]}

# ==================== Ù‡Ù†Ø¯Ù„Ø±Ù‡Ø§ ====================
user_states = {}

async def handle_start(message, args=""):
    user = message["from"]
    uid = user["id"]
    fname = user.get("first_name", "")
    uname = user.get("username", "")
    referred_by = None

    if args:
        try:
            referred_by = int(args)
            if referred_by == uid:
                referred_by = None
        except:
            pass

    add_user(uid, uname, fname, referred_by)

    if referred_by:
        referrer = get_user(referred_by)
        if referrer:
            got_star = add_referral(referred_by, uid)
            ref_count = get_user(referred_by)[3]
            msg = (f"ðŸŽ‰ ÛŒÚ© Ù†ÙØ± Ø¨Ø§ Ù„ÛŒÙ†Ú© Ø¯Ø¹ÙˆØª Ø´Ù…Ø§ Ø¹Ø¶Ùˆ Ø´Ø¯!\n\n"
                   f"ðŸ‘¤ Ú©Ø§Ø±Ø¨Ø±: {fname}\nðŸ†” Ø¢ÛŒØ¯ÛŒ: {uid}\n"
                   f"ðŸ“… Ø²Ù…Ø§Ù†: {datetime.now().strftime('%Y/%m/%d - %H:%M')}\n"
                   f"ðŸ‘¥ Ú©Ù„ Ø¯Ø¹ÙˆØªâ€ŒÙ‡Ø§ÛŒ Ø´Ù…Ø§: {ref_count}")
            if got_star:
                msg += "\n\nâ­ï¸ ØªØ¨Ø±ÛŒÚ©! ÛŒÚ© Ø§Ø³ØªØ§Ø± Ø¬Ø¯ÛŒØ¯ Ø¯Ø±ÛŒØ§ÙØª Ú©Ø±Ø¯ÛŒØ¯!"
            try:
                await send_message(referred_by, msg)
            except:
                pass
            reserve_msg = (f"ðŸ“¥ Ø±ÛŒÙØ±Ø§Ù„ Ø¬Ø¯ÛŒØ¯\n\nðŸ‘¤ Ú©Ø§Ø±Ø¨Ø±: {fname} | @{uname or 'Ù†Ø¯Ø§Ø±Ø¯'}\n"
                           f"ðŸ†” Ø¢ÛŒØ¯ÛŒ: {uid}\nðŸ‘¥ Ø¯Ø¹ÙˆØªâ€ŒÚ©Ù†Ù†Ø¯Ù‡: Ø¢ÛŒØ¯ÛŒ {referred_by}\n"
                           f"ðŸ“… Ø²Ù…Ø§Ù†: {datetime.now().strftime('%Y/%m/%d - %H:%M')}")
            try:
                await send_message(RESERVE_CHANNEL, reserve_msg)
            except:
                pass

    is_member = await check_membership(uid)
    if not is_member:
        await send_message(uid,
            f"Ø³Ù„Ø§Ù… {fname} Ø¹Ø²ÛŒØ²! ðŸ‘‹\n\nØ¨Ø±Ø§ÛŒ Ø§Ø³ØªÙØ§Ø¯Ù‡ Ø§Ø² Ø±Ø¨Ø§Øª Ù†Ø¨ÙˆÙ„Ø§ Ø§Ø³ØªØ§Ø±Ø²ØŒ Ù„Ø·ÙØ§Ù‹ Ø§Ø¨ØªØ¯Ø§ Ø¯Ø± Ú©Ø§Ù†Ø§Ù„â€ŒÙ‡Ø§ÛŒ Ø²ÛŒØ± Ø¹Ø¶Ùˆ Ø´ÙˆÛŒØ¯:",
            reply_markup=join_keyboard())
        return

    await send_message(uid,
        f"{EMOJI['welcome1']} Ø³Ù„Ø§Ù… {fname} Ø¹Ø²ÛŒØ²!\n\n"
        f"Ø¨Ù‡ Ø±Ø¨Ø§Øª Ø±Ø³Ù…ÛŒ Ù†Ø¨ÙˆÙ„Ø§ Ø§Ø³ØªØ§Ø±Ø² Ø®ÙˆØ´ Ø¢Ù…Ø¯ÛŒØ¯ {EMOJI['welcome2']}\n\n"
        f"Ø§Ø² Ù…Ù†ÙˆÛŒ Ø²ÛŒØ± Ú¯Ø²ÛŒÙ†Ù‡ Ù…ÙˆØ±Ø¯ Ù†Ø¸Ø± Ø®ÙˆØ¯ Ø±Ø§ Ø§Ù†ØªØ®Ø§Ø¨ Ú©Ù†ÛŒØ¯ {EMOJI['arrow']}",
        reply_markup=main_menu())

async def handle_callback(callback):
    cid = callback["id"]
    data = callback["data"]
    msg = callback["message"]
    chat_id = msg["chat"]["id"]
    msg_id = msg["message_id"]
    user = callback["from"]
    uid = user["id"]
    fname = user.get("first_name", "")
    uname = user.get("username", "")

    await answer_callback(cid)

    if data == "check_join":
        is_member = await check_membership(uid)
        if not is_member:
            await edit_message(chat_id, msg_id,
                "âš ï¸ Ù‡Ù†ÙˆØ² Ø¯Ø± Ù‡Ù…Ù‡ Ú©Ø§Ù†Ø§Ù„â€ŒÙ‡Ø§ Ø¹Ø¶Ùˆ Ù†Ø´Ø¯Ù‡â€ŒØ§ÛŒØ¯!\n\nÙ„Ø·ÙØ§Ù‹ Ø§Ø¨ØªØ¯Ø§ Ø¹Ø¶Ùˆ Ø´ÙˆÛŒØ¯:",
                reply_markup=join_keyboard())
            return
        await edit_message(chat_id, msg_id,
            f"{EMOJI['welcome1']} Ø³Ù„Ø§Ù… {fname} Ø¹Ø²ÛŒØ²!\n\n"
            f"Ø¨Ù‡ Ø±Ø¨Ø§Øª Ø±Ø³Ù…ÛŒ Ù†Ø¨ÙˆÙ„Ø§ Ø§Ø³ØªØ§Ø±Ø² Ø®ÙˆØ´ Ø¢Ù…Ø¯ÛŒØ¯ {EMOJI['welcome2']}\n\n"
            f"Ø§Ø² Ù…Ù†ÙˆÛŒ Ø²ÛŒØ± Ú¯Ø²ÛŒÙ†Ù‡ Ù…ÙˆØ±Ø¯ Ù†Ø¸Ø± Ø®ÙˆØ¯ Ø±Ø§ Ø§Ù†ØªØ®Ø§Ø¨ Ú©Ù†ÛŒØ¯ {EMOJI['arrow']}",
            reply_markup=main_menu())
        return

    is_member = await check_membership(uid)
    if not is_member:
        await edit_message(chat_id, msg_id,
            "âš ï¸ Ù„Ø·ÙØ§Ù‹ Ø§Ø¨ØªØ¯Ø§ Ø¯Ø± Ú©Ø§Ù†Ø§Ù„â€ŒÙ‡Ø§ÛŒ Ù…Ø§ Ø¹Ø¶Ùˆ Ø´ÙˆÛŒØ¯:",
            reply_markup=join_keyboard())
        return

    if data == "back_main":
        await edit_message(chat_id, msg_id,
            f"{EMOJI['welcome1']} Ø³Ù„Ø§Ù… {fname} Ø¹Ø²ÛŒØ²!\n\n"
            f"Ø§Ø² Ù…Ù†ÙˆÛŒ Ø²ÛŒØ± Ú¯Ø²ÛŒÙ†Ù‡ Ù…ÙˆØ±Ø¯ Ù†Ø¸Ø± Ø®ÙˆØ¯ Ø±Ø§ Ø§Ù†ØªØ®Ø§Ø¨ Ú©Ù†ÛŒØ¯ {EMOJI['arrow']}",
            reply_markup=main_menu())

    elif data == "stars":
        db_user = get_user(uid)
        ref_count = db_user[3] if db_user else 0
        stars = db_user[4] if db_user else 0
        remaining = STARS_PER_REFERRAL - (ref_count % STARS_PER_REFERRAL)
        if remaining == STARS_PER_REFERRAL:
            remaining = 0

        text = (f"{pe('5325547803936572038','âœ¨')} <b>Ø¨Ø®Ø´ Ø§Ø³ØªØ§Ø±Ø²</b>\n\n"
                f"{pe('5325547803936572038','âœ¨')} Ø§Ø³ØªØ§Ø±Ø²Ù‡Ø§ÛŒ Ú©Ø³Ø¨â€ŒØ´Ø¯Ù‡: <code>{stars}</code>\n"
                f"{pe('5397782960512444700','ðŸ“Œ')} Ø¨Ù‡ Ø§Ø²Ø§ÛŒ Ù‡Ø± <b>{STARS_PER_REFERRAL} Ø¯Ø¹ÙˆØª</b>ØŒ ÛŒÚ© Ø§Ø³ØªØ§Ø±Ø² Ø¬Ø§ÛŒØ²Ù‡ Ù…ÛŒâ€ŒÚ¯ÛŒØ±ÛŒØ¯!\n")
        if remaining > 0:
            text += f"{pe('5231012545799666522','ðŸ”')} ØªØ§ Ø§Ø³ØªØ§Ø±Ø² Ø¨Ø¹Ø¯ÛŒ: <b>{remaining} Ø¯Ø¹ÙˆØª Ø¯ÛŒÚ¯Ø±</b>"
        else:
            text += f"{pe('5206607081334906820','âœ”ï¸')} Ø´Ù…Ø§ ÙˆØ§Ø¬Ø¯ Ø´Ø±Ø§ÛŒØ· Ø¯Ø±ÛŒØ§ÙØª Ø§Ø³ØªØ§Ø±Ø² Ù‡Ø³ØªÛŒØ¯!"
        await edit_message(chat_id, msg_id, text, reply_markup=stars_keyboard())

    elif data == "referral":
        db_user = get_user(uid)
        ref_count = db_user[3] if db_user else 0
        link = f"https://t.me/{BOT_USERNAME}?start={uid}"
        await edit_message(chat_id, msg_id,
            f"{EMOJI['globe']} ØªÙˆØ¬Ù‡ Ø¯Ø§Ø´ØªÙ‡ Ø¨Ø§Ø´ÛŒØ¯ Ú©Ù‡ Ù‡Ø± 1 Ù†ÙØ± Ø¨Ø±Ø§Ø¨Ø± Ø¨Ø§ 1 Ø§Ù…ØªÛŒØ§Ø² Ù…ÛŒØ¨Ø§Ø´Ø¯.\n\n"
            f"Ù„ÛŒÙ†Ú© Ø±ÙØ±Ø§Ù„ Ø´Ù…Ø§ {EMOJI['linkarrow']}\n\n"
            f"{EMOJI['referral']} <code>{link}</code>\n\n"
            f"{pe('5231012545799666522','ðŸ”')} ØªØ¹Ø¯Ø§Ø¯ Ø¯Ø¹ÙˆØªâ€ŒÙ‡Ø§ÛŒ Ø´Ù…Ø§: <code>{ref_count}</code>",
            reply_markup=back_button())

    elif data == "get_referral":
        link = f"https://t.me/{BOT_USERNAME}?start={uid}"
        await edit_message(chat_id, msg_id,
            f"ðŸ”— <b>Ù„ÛŒÙ†Ú© Ø¯Ø¹ÙˆØª Ø§Ø®ØªØµØ§ØµÛŒ Ø´Ù…Ø§:</b>\n\n<code>{link}</code>\n\n"
            f"Ø§ÛŒÙ† Ù„ÛŒÙ†Ú© Ø±Ø§ Ø¨Ø§ Ø¯ÙˆØ³ØªØ§Ù† Ø®ÙˆØ¯ Ø¨Ù‡ Ø§Ø´ØªØ±Ø§Ú© Ø¨Ú¯Ø°Ø§Ø±ÛŒØ¯.\n"
            f"Ø¨Ù‡ Ø§Ø²Ø§ÛŒ Ù‡Ø± <b>{STARS_PER_REFERRAL} Ø¯Ø¹ÙˆØª</b> Ù…ÙˆÙÙ‚ØŒ ÛŒÚ© {EMOJI['starz']} Ø§Ø³ØªØ§Ø± Ø¯Ø±ÛŒØ§ÙØª Ù…ÛŒâ€ŒÚ©Ù†ÛŒØ¯!",
            reply_markup=back_button("stars"))

    elif data == "claim_star":
        db_user = get_user(uid)
        stars = db_user[4] if db_user else 0
        if stars <= 0:
            await edit_message(chat_id, msg_id,
                f"{pe('5271604874419647061','âš ï¸')} Ø´Ù…Ø§ Ø¯Ø± Ø­Ø§Ù„ Ø­Ø§Ø¶Ø± Ø§Ø³ØªØ§Ø±Ø²ÛŒ Ø¨Ø±Ø§ÛŒ Ø¯Ø±ÛŒØ§ÙØª Ù†Ø¯Ø§Ø±ÛŒØ¯.\n\n"
                f"{pe('5447644880824181073','ðŸ”—')} Ø¨Ù‡ Ø§Ø²Ø§ÛŒ Ù‡Ø± {STARS_PER_REFERRAL} Ø¯Ø¹ÙˆØªØŒ ÛŒÚ© Ø§Ø³ØªØ§Ø±Ø² Ú©Ø³Ø¨ Ù…ÛŒâ€ŒÚ©Ù†ÛŒØ¯!",
                reply_markup=back_button("stars"))
            return
        user_states[uid] = {"state": "waiting_post_link", "stars": stars}
        await edit_message(chat_id, msg_id,
            f"ðŸŽ Ø´Ù…Ø§ <b>{stars} Ø§Ø³ØªØ§Ø±</b> Ø¯Ø§Ø±ÛŒØ¯!\n\n"
            "Ù„Ø·ÙØ§Ù‹ Ù„ÛŒÙ†Ú© Ù¾Ø³ØªÛŒ Ú©Ù‡ Ù…ÛŒâ€ŒØ®ÙˆØ§Ù‡ÛŒØ¯ Ø§Ø³ØªØ§Ø± Ø±ÙˆÛŒ Ø¢Ù† Ø«Ø¨Øª Ø´ÙˆØ¯ Ø±Ø§ Ø§Ø±Ø³Ø§Ù„ Ú©Ù†ÛŒØ¯:\n\n"
            "ðŸ“Ž Ù…Ø«Ø§Ù„: <code>https://t.me/yourchannel/123</code>",
            reply_markup=back_button("stars"))

    elif data == "account":
        db_user = get_user(uid)
        ref_count = db_user[3] if db_user else 0
        stars = db_user[4] if db_user else 0
        username_text = f"@{uname}" if uname else "Ù†Ø¯Ø§Ø±Ø¯"
        is_owner = uid == OWNER_ID
        owner_line = f"\n{EMOJI['owner']} Ù…Ø§Ù„Ú© Ø±Ø¨Ø§Øª\n" if is_owner else ""

        await edit_message(chat_id, msg_id,
            f"{EMOJI['acctitle']} Ø­Ø³Ø§Ø¨ Ú©Ø§Ø±Ø¨Ø±ÛŒ Ø´Ù…Ø§{owner_line}\n\n"
            f"{EMOJI['name']} Ù†Ø§Ù…: {fname}\n"
            f"{EMOJI['id']} Ø¢ÛŒØ¯ÛŒ: <code>{uid}</code>\n"
            f"{EMOJI['username']} ÛŒÙˆØ²Ø±Ù†ÛŒÙ…: {username_text}\n\n"
            f"{EMOJI['invites']} ØªØ¹Ø¯Ø§Ø¯ Ø¯Ø¹ÙˆØªâ€ŒÙ‡Ø§: <code>{ref_count}</code>\n"
            f"{EMOJI['starz']} Ø§Ø³ØªØ§Ø±Ø²Ù‡Ø§ÛŒ Ù…ÙˆØ¬ÙˆØ¯: <code>{stars}</code>",
            reply_markup=back_button())

    elif data == "support":
        user_states[uid] = {"state": "waiting_support"}
        await edit_message(chat_id, msg_id,
            f"{pe('5251203410396458957','ðŸ›¡')} <b>Ø¨Ø®Ø´ Ù¾Ø´ØªÛŒØ¨Ø§Ù†ÛŒ</b>\n\n"
            f"{pe('5440621591387980068','ðŸ”œ')} Ù¾ÛŒØ§Ù… ÛŒØ§ Ù…Ø´Ú©Ù„ Ø®ÙˆØ¯ Ø±Ø§ Ø¨Ù†ÙˆÛŒØ³ÛŒØ¯ Ùˆ Ø§Ø±Ø³Ø§Ù„ Ú©Ù†ÛŒØ¯.\n"
            "Ú©Ø§Ø±Ø´Ù†Ø§Ø³Ø§Ù† Ù…Ø§ Ø¯Ø± Ø§Ø³Ø±Ø¹ ÙˆÙ‚Øª Ù¾Ø§Ø³Ø® Ø®ÙˆØ§Ù‡Ù†Ø¯ Ø¯Ø§Ø¯. ðŸ™",
            reply_markup=back_button())

async def handle_message(message):
    user = message["from"]
    uid = user["id"]
    fname = user.get("first_name", "")
    uname = user.get("username", "")
    text = message.get("text", "")

    # Ù¾Ø§Ø³Ø® Ø§Ø¯Ù…ÛŒÙ† Ø¨Ù‡ ØªÛŒÚ©Øª
    if uid == OWNER_ID and message.get("reply_to_message"):
        orig = message["reply_to_message"].get("text", "")
        if "ØªÛŒÚ©Øª Ø´Ù…Ø§Ø±Ù‡" in orig:
            for line in orig.split("\n"):
                if "Ø¢ÛŒØ¯ÛŒ:" in line:
                    try:
                        target_uid = int(line.split(":")[1].strip())
                        await send_message(target_uid,
                            f"ðŸ“© <b>Ù¾Ø§Ø³Ø® Ù¾Ø´ØªÛŒØ¨Ø§Ù†ÛŒ Ù†Ø¨ÙˆÙ„Ø§:</b>\n\n{text}")
                        await send_message(uid, "âœ… Ù¾Ø§Ø³Ø® Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø§Ø±Ø³Ø§Ù„ Ø´Ø¯.")
                    except:
                        await send_message(uid, "âš ï¸ Ø®Ø·Ø§ Ø¯Ø± Ø§Ø±Ø³Ø§Ù„ Ù¾Ø§Ø³Ø®.")
                    return

    # Ø¯Ø³ØªÙˆØ±Ø§Øª Ø§Ø¯Ù…ÛŒÙ†
    if text.startswith("/done") and uid == OWNER_ID:
        parts = text.split()
        if len(parts) < 3:
            await send_message(uid, "âš ï¸ ÙØ±Ù…Øª: /done [user_id] [request_id]")
            return
        try:
            target_uid = int(parts[1])
            req_id = int(parts[2])

            # Ú¯Ø±ÙØªÙ† Ø§Ø·Ù„Ø§Ø¹Ø§Øª Ø¯Ø±Ø®ÙˆØ§Ø³Øª
            conn = sqlite3.connect("nebula.db")
            c = conn.cursor()
            c.execute("SELECT post_link FROM star_requests WHERE id = ?", (req_id,))
            row = c.fetchone()
            post_link = row[0] if row else "Ù†Ø§Ù…Ø´Ø®Øµ"
            conn.close()

            # Ú¯Ø±ÙØªÙ† Ø§Ø·Ù„Ø§Ø¹Ø§Øª Ú©Ø§Ø±Ø¨Ø±
            db_user = get_user(target_uid)
            fname = db_user[2] if db_user else str(target_uid)
            stars = (db_user[4] if db_user else 0)

            done_request(target_uid, req_id)

            # Ù¾ÛŒØ§Ù… Ø¨Ù‡ Ú©Ø§Ø±Ø¨Ø±
            await send_message(target_uid,
                f"{pe('5206607081334906820','âœ”ï¸')} <b>Ø§Ø³ØªØ§Ø±Ø² Ø´Ù…Ø§ Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø«Ø¨Øª Ø´Ø¯!</b>\n\n"
                "Ù…Ù…Ù†ÙˆÙ† Ø§Ø² Ø§ÛŒÙ†Ú©Ù‡ Ø¯Ø± Ù†Ø¨ÙˆÙ„Ø§ Ø§Ø³ØªØ§Ø±Ø² ÙØ¹Ø§Ù„ Ù‡Ø³ØªÛŒØ¯. ðŸ’«")

            # Ù¾ÛŒØ§Ù… Ø¹Ù…ÙˆÙ…ÛŒ Ø¨Ù‡ Ú©Ø§Ù†Ø§Ù„ NebulaRefaccept
            public_msg = (
                f"{pe('5438496463044752972','â­ï¸')} <b>Ø¯Ø±Ø®ÙˆØ§Ø³Øª Ø¬Ø¯ÛŒØ¯</b>\n\n"
                f"{pe('5461117441612462242','ðŸ™‚')} Ú©Ø§Ø±Ø¨Ø±: {fname}\n"
                f"{pe('5447644880824181073','ðŸ”—')} Ù„ÛŒÙ†Ú© Ù¾Ø³Øª: {post_link}\n"
                f"{pe('5325547803936572038','âœ¨')} ØªØ¹Ø¯Ø§Ø¯ Ø§Ø³ØªØ§Ø±Ø²: {stars}\n\n"
                f"{pe('5206607081334906820','âœ”ï¸')} Ø§Ù†Ø¬Ø§Ù… Ø´Ø¯"
            )
            register_btn = {
                "inline_keyboard": [[
                    {"text": "âœ¨ Ø³ÙØ§Ø±Ø´ Ø®ÙˆØ¯ Ø±Ø§ Ø«Ø¨Øª Ú©Ù†ÛŒØ¯ âœ¨",
                     "url": f"https://t.me/{BOT_USERNAME}",
                     "icon_custom_emoji_id": "5325547803936572038"}
                ]]
            }
            await send_message(-1004347111274, public_msg, reply_markup=register_btn)
            await send_message(uid, f"âœ… Ø§Ø³ØªØ§Ø±Ø² Ú©Ø§Ø±Ø¨Ø± {target_uid} Ø«Ø¨Øª Ø´Ø¯.")
        except Exception as e:
            await send_message(uid, f"âš ï¸ Ø®Ø·Ø§: {e}")
        return

    if text.startswith("/stats") and uid == OWNER_ID:
        total, refs, pending, tickets = get_stats()
        await send_message(uid,
            f"ðŸ“Š <b>Ø¢Ù…Ø§Ø± Ø±Ø¨Ø§Øª Ù†Ø¨ÙˆÙ„Ø§</b>\n\n"
            f"ðŸ‘¥ Ú©Ù„ Ú©Ø§Ø±Ø¨Ø±Ø§Ù†: <code>{total}</code>\n"
            f"ðŸ”— Ú©Ù„ Ø±ÛŒÙØ±Ø§Ù„â€ŒÙ‡Ø§: <code>{refs}</code>\n"
            f"â­ï¸ Ø¯Ø±Ø®ÙˆØ§Ø³Øªâ€ŒÙ‡Ø§ÛŒ Ø¯Ø± Ø§Ù†ØªØ¸Ø§Ø±: <code>{pending}</code>\n"
            f"ðŸŽ« ØªÛŒÚ©Øªâ€ŒÙ‡Ø§ÛŒ Ø¨Ø§Ø²: <code>{tickets}</code>")
        return

    if text.startswith("/start"):
        args = text.split(" ")[1] if " " in text else ""
        await handle_start(message, args)
        return

    state_data = user_states.get(uid, {})
    state = state_data.get("state")

    if state == "waiting_post_link":
        user_states.pop(uid, None)
        stars = state_data.get("stars", 1)
        req_id = add_star_request(uid, text)
        reserve_msg = (
            f"{pe('5253742260054409879','âœ‰ï¸')} <b>Ø¯Ø±Ø®ÙˆØ§Ø³Øª Ø§Ø³ØªØ§Ø±Ø² Ø¬Ø¯ÛŒØ¯</b>\n\n"
            f"{pe('5210956306952758910','ðŸ‘€')} Ú©Ø§Ø±Ø¨Ø±: {fname}\n"
            f"{pe('5303479226882603449','ðŸ˜¯')} Ø¢ÛŒØ¯ÛŒ: <code>{uid}</code>\n"
            f"{pe('5276032951342088188','ðŸ’¥')} ÛŒÙˆØ²Ø±Ù†ÛŒÙ…: @{uname or 'Ù†Ø¯Ø§Ø±Ø¯'}\n"
            f"{pe('5413879192267805083','ðŸ—“')} Ø²Ù…Ø§Ù†: {datetime.now().strftime('%Y/%m/%d - %H:%M')}\n"
            f"ðŸ”— Ù„ÛŒÙ†Ú© Ù¾Ø³Øª: {text}\nâ­ï¸ ØªØ¹Ø¯Ø§Ø¯ Ø§Ø³ØªØ§Ø±Ø²: {stars}\n"
            f"ðŸ†” Ø´Ù…Ø§Ø±Ù‡ Ø¯Ø±Ø®ÙˆØ§Ø³Øª: #{req_id}\n\n"
            f"Ù¾Ø³ Ø§Ø² Ø«Ø¨ØªØŒ Ø¯Ø³ØªÙˆØ± Ø²ÛŒØ± Ø±Ø§ Ø§Ø±Ø³Ø§Ù„ Ú©Ù†ÛŒØ¯:\n"
            f"<code>/done {uid} {req_id}</code>"
        )
        try:
            await send_message(RESERVE_CHANNEL, reserve_msg)
        except:
            pass
        try:
            await send_message(OWNER_ID, reserve_msg)
        except:
            pass
        await send_message(uid,
            f"âœ… <b>Ø¯Ø±Ø®ÙˆØ§Ø³Øª Ø´Ù…Ø§ Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø«Ø¨Øª Ø´Ø¯!</b>\n\n"
            f"ðŸ”— Ù„ÛŒÙ†Ú© Ù¾Ø³Øª: {text}\nâ­ï¸ ØªØ¹Ø¯Ø§Ø¯ Ø§Ø³ØªØ§Ø±: {stars}\n\n"
            "Ù¾Ø³ Ø§Ø² Ø¨Ø±Ø±Ø³ÛŒØŒ Ø§Ø³ØªØ§Ø± Ø´Ù…Ø§ Ø«Ø¨Øª Ø®ÙˆØ§Ù‡Ø¯ Ø´Ø¯. ðŸ™",
            reply_markup=main_menu())

    elif state == "waiting_support":
        user_states.pop(uid, None)
        ticket_id = add_ticket(uid, text)
        ticket_msg = (
            f"ðŸŽ« <b>ØªÛŒÚ©Øª Ø´Ù…Ø§Ø±Ù‡ #{ticket_id}</b>\n\n"
            f"ðŸ‘¤ Ú©Ø§Ø±Ø¨Ø±: {fname}\nðŸ†” Ø¢ÛŒØ¯ÛŒ: <code>{uid}</code>\n"
            f"ðŸ“Ž ÛŒÙˆØ²Ø±Ù†ÛŒÙ…: @{uname or 'Ù†Ø¯Ø§Ø±Ø¯'}\n"
            f"ðŸ“… Ø²Ù…Ø§Ù†: {datetime.now().strftime('%Y/%m/%d - %H:%M')}\n\n"
            f"ðŸ’¬ Ù¾ÛŒØ§Ù…:\n{text}\n\nØ¨Ø±Ø§ÛŒ Ù¾Ø§Ø³Ø®ØŒ Ø±ÙˆÛŒ Ø§ÛŒÙ† Ù¾ÛŒØ§Ù… Reply Ú©Ù†ÛŒØ¯."
        )
        try:
            await send_message(OWNER_ID, ticket_msg)
        except:
            pass
        try:
            await send_message(RESERVE_CHANNEL, ticket_msg)
        except:
            pass
        await send_message(uid,
            f"âœ… <b>ØªÛŒÚ©Øª Ø´Ù…Ø§ Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø«Ø¨Øª Ø´Ø¯!</b>\n\n"
            f"ðŸŽ« Ø´Ù…Ø§Ø±Ù‡ ØªÛŒÚ©Øª: #{ticket_id}\n\n"
            "Ú©Ø§Ø±Ø´Ù†Ø§Ø³Ø§Ù† Ù…Ø§ Ø¨Ù‡ Ø²ÙˆØ¯ÛŒ Ù¾Ø§Ø³Ø® Ø®ÙˆØ§Ù‡Ù†Ø¯ Ø¯Ø§Ø¯. ðŸ™",
            reply_markup=main_menu())
    else:
        await send_message(uid,
            f"Ø§Ø² Ù…Ù†ÙˆÛŒ Ø²ÛŒØ± Ú¯Ø²ÛŒÙ†Ù‡ Ù…ÙˆØ±Ø¯ Ù†Ø¸Ø± Ø±Ø§ Ø§Ù†ØªØ®Ø§Ø¨ Ú©Ù†ÛŒØ¯ {EMOJI['arrow']}",
            reply_markup=main_menu())

# ==================== Ù¾ÙˆÙ„ÛŒÙ†Ú¯ ====================
async def main():
    init_db()
    offset = None
    print("âœ… Ø±Ø¨Ø§Øª Ù†Ø¨ÙˆÙ„Ø§ Ø§Ø³ØªØ§Ø±Ø² Ø¯Ø± Ø­Ø§Ù„ Ø§Ø¬Ø±Ø§Ø³Øª...")
    async with httpx.AsyncClient() as client:
        while True:
            try:
                params = {"timeout": 30}
                if offset:
                    params["offset"] = offset
                r = await client.get(f"{BASE_URL}/getUpdates", params=params, timeout=35)
                data = r.json()
                if not data.get("ok"):
                    await asyncio.sleep(2)
                    continue
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    try:
                        if "message" in update:
                            await handle_message(update["message"])
                        elif "callback_query" in update:
                            await handle_callback(update["callback_query"])
                    except Exception as e:
                        logging.error(f"Error handling update: {e}")
            except Exception as e:
                logging.error(f"Polling error: {e}")
                await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
