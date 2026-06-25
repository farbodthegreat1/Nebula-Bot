import httpx
import sqlite3
import asyncio
import logging
from datetime import datetime

# ==================== تنظیمات ====================
TOKEN = "8600298019:AAGuH6U-BKB3O30LbJAOubB4A01Yy8_TDMI"
OWNER_ID = 1374081605
RESERVE_CHANNEL = -1003764301938
REQUIRED_CHANNELS = ["@Nebulastars", "@Nebulastarsgp"]
BOT_USERNAME = "Nebularefbot"
STARS_PER_REFERRAL = 3
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

# ==================== ایموجی پریمیوم ====================
def pe(emoji_id, fallback="⭐"):
    return f"<tg-emoji emoji-id='{emoji_id}'>{fallback}</tg-emoji>"

EMOJI = {
    "stars":    pe("5803311247159988988", "⭐"),
    "account":  pe("5875255350982087963", "👤"),
    "support":  pe("5803311247159988988", "🎧"),
    "welcome1": pe("5893189613991759811", "💥"),
    "welcome2": pe("5809695698865623554", "🌟"),
    "arrow":    pe("5803120932864136855", "👇"),
    "name":     pe("5217822164362739968", "👑"),
    "id":       pe("5422439311196834318", "💡"),
    "username": pe("5424972470023104089", "🔥"),
    "invites":  pe("5415655814079723871", "🔝"),
    "starz":    pe("5325547803936572038", "✨"),
    "owner":    pe("5438496463044752972", "⭐"),
    "back":     pe("5416041192905265756", "🔙"),
    "acctitle": pe("5461117441612462242", "😊"),
    "referral": pe("5305265301917549162", "🔗"),
    "globe":    pe("5447410659077661506", "🌐"),
    "linkarrow":pe("5803120932864136855", "👇"),
}


# ==================== دیتابیس ====================
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

# ==================== API تلگرام ====================
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

# ==================== کیبوردها ====================
def main_menu():
    return {
        "inline_keyboard": [[
            {"text": "استارز", "callback_data": "stars", "icon_custom_emoji_id": "5803311247159988988"},
            {"text": "ریفرال", "callback_data": "referral", "icon_custom_emoji_id": "5305265301917549162"}
        ], [
            {"text": "حساب کاربری", "callback_data": "account", "icon_custom_emoji_id": "5875255350982087963"},
            {"text": "پشتیبانی", "callback_data": "support", "icon_custom_emoji_id": "5803311247159988988"}
        ]]
    }

def join_keyboard():
    buttons = []
    for ch in REQUIRED_CHANNELS:
        buttons.append([{"text": f"عضویت در {ch}", "url": f"https://t.me/{ch[1:]}"}])
    buttons.append([{"text": "✅ عضو شدم", "callback_data": "check_join"}])
    return {"inline_keyboard": buttons}

def back_button(cb="back_main"):
    return {"inline_keyboard": [[
        {"text": "بازگشت", "callback_data": cb, "icon_custom_emoji_id": "5416041192905265756"}
    ]]}

def stars_keyboard():
    return {"inline_keyboard": [
        [{"text": "دریافت استار", "callback_data": "claim_star", "icon_custom_emoji_id": "5325547803936572038"}],
        [{"text": "بازگشت", "callback_data": "back_main", "icon_custom_emoji_id": "5416041192905265756"}]
    ]}

# ==================== هندلرها ====================
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
            msg = (f"🎉 یک نفر با لینک دعوت شما عضو شد!\n\n"
                   f"👤 کاربر: {fname}\n🆔 آیدی: {uid}\n"
                   f"📅 زمان: {datetime.now().strftime('%Y/%m/%d - %H:%M')}\n"
                   f"👥 کل دعوت‌های شما: {ref_count}")
            if got_star:
                msg += "\n\n⭐️ تبریک! یک استار جدید دریافت کردید!"
            try:
                await send_message(referred_by, msg)
            except:
                pass
            reserve_msg = (f"📥 ریفرال جدید\n\n👤 کاربر: {fname} | @{uname or 'ندارد'}\n"
                           f"🆔 آیدی: {uid}\n👥 دعوت‌کننده: آیدی {referred_by}\n"
                           f"📅 زمان: {datetime.now().strftime('%Y/%m/%d - %H:%M')}")
            try:
                await send_message(RESERVE_CHANNEL, reserve_msg)
            except:
                pass

    is_member = await check_membership(uid)
    if not is_member:
        await send_message(uid,
            f"سلام {fname} عزیز! 👋\n\nبرای استفاده از ربات نبولا استارز، لطفاً ابتدا در کانال‌های زیر عضو شوید:",
            reply_markup=join_keyboard())
        return

    await send_message(uid,
        f"{EMOJI['welcome1']} سلام {fname} عزیز!\n\n"
        f"به ربات رسمی نبولا استارز خوش آمدید {EMOJI['welcome2']}\n\n"
        f"از منوی زیر گزینه مورد نظر خود را انتخاب کنید {EMOJI['arrow']}",
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
                "⚠️ هنوز در همه کانال‌ها عضو نشده‌اید!\n\nلطفاً ابتدا عضو شوید:",
                reply_markup=join_keyboard())
            return
        await edit_message(chat_id, msg_id,
            f"{EMOJI['welcome1']} سلام {fname} عزیز!\n\n"
            f"به ربات رسمی نبولا استارز خوش آمدید {EMOJI['welcome2']}\n\n"
            f"از منوی زیر گزینه مورد نظر خود را انتخاب کنید {EMOJI['arrow']}",
            reply_markup=main_menu())
        return

    is_member = await check_membership(uid)
    if not is_member:
        await edit_message(chat_id, msg_id,
            "⚠️ لطفاً ابتدا در کانال‌های ما عضو شوید:",
            reply_markup=join_keyboard())
        return

    if data == "back_main":
        await edit_message(chat_id, msg_id,
            f"{EMOJI['welcome1']} سلام {fname} عزیز!\n\n"
            f"از منوی زیر گزینه مورد نظر خود را انتخاب کنید {EMOJI['arrow']}",
            reply_markup=main_menu())

    elif data == "stars":
        db_user = get_user(uid)
        ref_count = db_user[3] if db_user else 0
        stars = db_user[4] if db_user else 0
        remaining = STARS_PER_REFERRAL - (ref_count % STARS_PER_REFERRAL)
        if remaining == STARS_PER_REFERRAL:
            remaining = 0

        text = (f"{EMOJI['starz']} <b>بخش استارز</b>\n\n"
                f"👥 تعداد دعوت‌های شما: <code>{ref_count}</code>\n"
                f"{EMOJI['starz']} استارزهای کسب‌شده: <code>{stars}</code>\n\n"
                f"📌 به ازای هر <b>{STARS_PER_REFERRAL} دعوت</b>، یک استار جایزه می‌گیرید!\n")
        if remaining > 0:
            text += f"🔄 تا استار بعدی: <b>{remaining} دعوت دیگر</b>"
        else:
            text += "✅ شما واجد شرایط دریافت استار هستید!"
        await edit_message(chat_id, msg_id, text, reply_markup=stars_keyboard())

    elif data == "referral":
        db_user = get_user(uid)
        ref_count = db_user[3] if db_user else 0
        link = f"https://t.me/{BOT_USERNAME}?start={uid}"
        await edit_message(chat_id, msg_id,
            f"{EMOJI['globe']} توجه داشته باشید که هر 1 نفر برابر با 1 امتیاز میباشد.\n\n"
            f"لینک رفرال شما {EMOJI['linkarrow']}\n\n"
            f"{EMOJI['referral']} <code>{link}</code>\n\n"
            f"👥 تعداد دعوت‌های شما: <code>{ref_count}</code>",
            reply_markup=back_button())

    elif data == "get_referral":
        link = f"https://t.me/{BOT_USERNAME}?start={uid}"
        await edit_message(chat_id, msg_id,
            f"🔗 <b>لینک دعوت اختصاصی شما:</b>\n\n<code>{link}</code>\n\n"
            f"این لینک را با دوستان خود به اشتراک بگذارید.\n"
            f"به ازای هر <b>{STARS_PER_REFERRAL} دعوت</b> موفق، یک {EMOJI['starz']} استار دریافت می‌کنید!",
            reply_markup=back_button("stars"))

    elif data == "claim_star":
        db_user = get_user(uid)
        stars = db_user[4] if db_user else 0
        if stars <= 0:
            await edit_message(chat_id, msg_id,
                f"⚠️ شما در حال حاضر استاری برای دریافت ندارید.\n\n"
                f"به ازای هر {STARS_PER_REFERRAL} دعوت، یک استار کسب می‌کنید! 🔗",
                reply_markup=back_button("stars"))
            return
        user_states[uid] = {"state": "waiting_post_link", "stars": stars}
        await edit_message(chat_id, msg_id,
            f"🎁 شما <b>{stars} استار</b> دارید!\n\n"
            "لطفاً لینک پستی که می‌خواهید استار روی آن ثبت شود را ارسال کنید:\n\n"
            "📎 مثال: <code>https://t.me/yourchannel/123</code>",
            reply_markup=back_button("stars"))

    elif data == "account":
        db_user = get_user(uid)
        ref_count = db_user[3] if db_user else 0
        stars = db_user[4] if db_user else 0
        username_text = f"@{uname}" if uname else "ندارد"
        is_owner = uid == OWNER_ID
        owner_line = f"\n{EMOJI['owner']} مالک ربات\n" if is_owner else ""

        await edit_message(chat_id, msg_id,
            f"{EMOJI['acctitle']} حساب کاربری شما{owner_line}\n\n"
            f"{EMOJI['name']} نام: {fname}\n"
            f"{EMOJI['id']} آیدی: <code>{uid}</code>\n"
            f"{EMOJI['username']} یوزرنیم: {username_text}\n\n"
            f"{EMOJI['invites']} تعداد دعوت‌ها: <code>{ref_count}</code>\n"
            f"{EMOJI['starz']} استارزهای موجود: <code>{stars}</code>",
            reply_markup=back_button())

    elif data == "support":
        user_states[uid] = {"state": "waiting_support"}
        await edit_message(chat_id, msg_id,
            "🎧 <b>بخش پشتیبانی</b>\n\n"
            "پیام یا مشکل خود را بنویسید و ارسال کنید.\n"
            "کارشناسان ما در اسرع وقت پاسخ خواهند داد. 🙏",
            reply_markup=back_button())

async def handle_message(message):
    user = message["from"]
    uid = user["id"]
    fname = user.get("first_name", "")
    uname = user.get("username", "")
    text = message.get("text", "")

    # پاسخ ادمین به تیکت
    if uid == OWNER_ID and message.get("reply_to_message"):
        orig = message["reply_to_message"].get("text", "")
        if "تیکت شماره" in orig:
            for line in orig.split("\n"):
                if "آیدی:" in line:
                    try:
                        target_uid = int(line.split(":")[1].strip())
                        await send_message(target_uid,
                            f"📩 <b>پاسخ پشتیبانی نبولا:</b>\n\n{text}")
                        await send_message(uid, "✅ پاسخ با موفقیت ارسال شد.")
                    except:
                        await send_message(uid, "⚠️ خطا در ارسال پاسخ.")
                    return

    # دستورات ادمین
    if text.startswith("/done") and uid == OWNER_ID:
        parts = text.split()
        if len(parts) < 3:
            await send_message(uid, "⚠️ فرمت: /done [user_id] [request_id]")
            return
        try:
            target_uid = int(parts[1])
            req_id = int(parts[2])
            done_request(target_uid, req_id)
            await send_message(target_uid,
                f"{EMOJI['starz']} <b>استار شما با موفقیت ثبت شد!</b>\n\n"
                "ممنون از اینکه در نبولا استارز فعال هستید. 💫")
            await send_message(uid, f"✅ استار کاربر {target_uid} ثبت شد.")
        except Exception as e:
            await send_message(uid, f"⚠️ خطا: {e}")
        return

    if text.startswith("/stats") and uid == OWNER_ID:
        total, refs, pending, tickets = get_stats()
        await send_message(uid,
            f"📊 <b>آمار ربات نبولا</b>\n\n"
            f"👥 کل کاربران: <code>{total}</code>\n"
            f"🔗 کل ریفرال‌ها: <code>{refs}</code>\n"
            f"⭐️ درخواست‌های در انتظار: <code>{pending}</code>\n"
            f"🎫 تیکت‌های باز: <code>{tickets}</code>")
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
            f"⭐️ <b>درخواست استار جدید</b>\n\n"
            f"👤 کاربر: {fname}\n🆔 آیدی: <code>{uid}</code>\n"
            f"📎 یوزرنیم: @{uname or 'ندارد'}\n"
            f"🔗 لینک پست: {text}\n⭐️ تعداد استار: {stars}\n"
            f"📅 زمان: {datetime.now().strftime('%Y/%m/%d - %H:%M')}\n"
            f"🆔 شماره درخواست: #{req_id}\n\n"
            f"پس از ثبت، دستور زیر را ارسال کنید:\n"
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
            f"✅ <b>درخواست شما با موفقیت ثبت شد!</b>\n\n"
            f"🔗 لینک پست: {text}\n⭐️ تعداد استار: {stars}\n\n"
            "پس از بررسی، استار شما ثبت خواهد شد. 🙏",
            reply_markup=main_menu())

    elif state == "waiting_support":
        user_states.pop(uid, None)
        ticket_id = add_ticket(uid, text)
        ticket_msg = (
            f"🎫 <b>تیکت شماره #{ticket_id}</b>\n\n"
            f"👤 کاربر: {fname}\n🆔 آیدی: <code>{uid}</code>\n"
            f"📎 یوزرنیم: @{uname or 'ندارد'}\n"
            f"📅 زمان: {datetime.now().strftime('%Y/%m/%d - %H:%M')}\n\n"
            f"💬 پیام:\n{text}\n\nبرای پاسخ، روی این پیام Reply کنید."
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
            f"✅ <b>تیکت شما با موفقیت ثبت شد!</b>\n\n"
            f"🎫 شماره تیکت: #{ticket_id}\n\n"
            "کارشناسان ما به زودی پاسخ خواهند داد. 🙏",
            reply_markup=main_menu())
    else:
        await send_message(uid,
            f"از منوی زیر گزینه مورد نظر را انتخاب کنید {EMOJI['arrow']}",
            reply_markup=main_menu())

# ==================== پولینگ ====================
async def main():
    init_db()
    offset = None
    print("✅ ربات نبولا استارز در حال اجراست...")
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
