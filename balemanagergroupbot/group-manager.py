import telebot
from telebot import types
import time
import re
from datetime import datetime, timedelta
import sqlite3
import json

# توکن ربات خود را وارد کنید
TOKEN = "1213045684:ER8D9DnlMMHJXpwFs4XHIXx8_ANstchkH58"
bot = telebot.TeleBot(TOKEN)

# ایجاد دیتابیس برای ذخیره تنظیمات و آمار
conn = sqlite3.connect('group_bot.db', check_same_thread=False)
c = conn.cursor()

# ایجاد جداول مورد نیاز
c.execute('''CREATE TABLE IF NOT EXISTS group_settings
             (group_id INTEGER PRIMARY KEY, 
              welcome_message TEXT,
              goodbye_message TEXT,
              anti_spam BOOLEAN,
              anti_link BOOLEAN,
              auto_delete_commands BOOLEAN)''')

c.execute('''CREATE TABLE IF NOT EXISTS user_warnings
             (user_id INTEGER, group_id INTEGER, warnings INTEGER,
              PRIMARY KEY (user_id, group_id))''')

# جدول جدید برای ذخیره کلمات فیلتر شده
c.execute('''CREATE TABLE IF NOT EXISTS filtered_words
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              group_id INTEGER,
              word TEXT,
              severity TEXT DEFAULT 'warning',  -- 'warning' یا 'ban'
              UNIQUE(group_id, word))''')

conn.commit()

# دیکشنری برای مدیریت موقت کاربران
user_messages = {}

# ================ دستورات پایه ================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "🤖 به ربات مدیریت گروه خوش آمدید!\n"
                          "برای مشاهده لیست دستورات از /help استفاده کنید.")

@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = """
📋 **لیست دستورات ربات:**

👑 **دستورات ادمین:**
/ban - بن کردن کاربر (ریپلی کنید)
/unban - آنبن کاربر (ریپلی کنید)
/kick - اخراج موقت کاربر
/mute - سکوت کاربر (ریپلی کنید)
/unmute - لغو سکوت
/warn - اخطار به کاربر
/warnings - مشاهده اخطارهای کاربر
/del - حذف پیام (ریپلی کنید)
/pin - سنجاق کردن پیام
/unpin - لغو سنجاق

⚙️ **تنظیمات گروه:**
/setwelcome [متن] - تنظیم پیام خوش‌آمدگویی
/setgoodbye [متن] - تنظیم پیام خداحافظی
/antispam on/off - فعال/غیرفعال کردن ضد اسپم
/antilink on/off - فعال/غیرفعال کردن ضد لینک
/admins - لیست ادمین‌ها

🔤 **مدیریت فیلتر کلمات:**
/addfilter [کلمه] [severity] - اضافه کردن کلمه به فیلتر (severity: warning یا ban)
/removefilter [کلمه] - حذف کلمه از فیلتر
/listfilters - نمایش لیست کلمات فیلتر شده
/clearfilters - پاک کردن همه کلمات فیلتر شده

📊 **آمار:**
/stats - آمار گروه
/about - درباره ربات
    """
    bot.reply_to(message, help_text, parse_mode="Markdown")

# ================ مدیریت اعضا ================

@bot.message_handler(commands=['ban'])
def ban_user(message):
    if not is_admin(message):
        bot.reply_to(message, "⛔️ این دستور فقط برای ادمین‌هاست!")
        return
    
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        reason = message.text.replace('/ban', '').strip()
        try:
            bot.ban_chat_member(message.chat.id, user_id)
            ban_msg = f"✅ کاربر {message.reply_to_message.from_user.first_name} بن شد."
            if reason:
                ban_msg += f"\n📝 دلیل: {reason}"
            bot.reply_to(message, ban_msg)
        except:
            bot.reply_to(message, "❌ خطا در بن کردن کاربر!")

@bot.message_handler(commands=['unban'])
def unban_user(message):
    if not is_admin(message):
        bot.reply_to(message, "⛔️ این دستور فقط برای ادمین‌هاست!")
        return
    
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        try:
            bot.unban_chat_member(message.chat.id, user_id)
            bot.reply_to(message, f"✅ آنبن شد.")
        except:
            bot.reply_to(message, "❌ خطا در آنبن کردن!")

@bot.message_handler(commands=['kick'])
def kick_user(message):
    if not is_admin(message):
        bot.reply_to(message, "⛔️ این دستور فقط برای ادمین‌هاست!")
        return
    
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        try:
            bot.ban_chat_member(message.chat.id, user_id)
            bot.unban_chat_member(message.chat.id, user_id)
            bot.reply_to(message, f"✅ کاربر اخراج شد.")
        except:
            bot.reply_to(message, "❌ خطا در اخراج کاربر!")

@bot.message_handler(commands=['mute'])
def mute_user(message):
    if not is_admin(message):
        bot.reply_to(message, "⛔️ این دستور فقط برای ادمین‌هاست!")
        return
    
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        # بررسی زمان وارد شده توسط کاربر
        args = message.text.replace('/mute', '').strip().split()
        mute_time = 3600  # پیش‌فرض 1 ساعت
        
        if args and args[0].isdigit():
            mute_time = int(args[0]) * 60  # تبدیل دقیقه به ثانیه
        
        try:
            until_date = int(time.time()) + mute_time
            bot.restrict_chat_member(message.chat.id, user_id, until_date=until_date, can_send_messages=False)
            bot.reply_to(message, f"✅ کاربر برای {mute_time//60} دقیقه سکوت کرد.")
        except:
            bot.reply_to(message, "❌ خطا در سکوت کاربر!")

# ================ سیستم اخطار ================

@bot.message_handler(commands=['warn'])
def warn_user(message):
    if not is_admin(message):
        bot.reply_to(message, "⛔️ این دستور فقط برای ادمین‌هاست!")
        return
    
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        group_id = message.chat.id
        reason = message.text.replace('/warn', '').strip()
        
        # بررسی تعداد اخطارهای قبلی
        c.execute("SELECT warnings FROM user_warnings WHERE user_id=? AND group_id=?", (user_id, group_id))
        result = c.fetchone()
        
        if result:
            warnings = result[0] + 1
            c.execute("UPDATE user_warnings SET warnings=? WHERE user_id=? AND group_id=?", (warnings, user_id, group_id))
        else:
            warnings = 1
            c.execute("INSERT INTO user_warnings VALUES (?, ?, ?)", (user_id, group_id, warnings))
        
        conn.commit()
        
        warn_msg = f"⚠️ کاربر اخطار {warnings}/3 دریافت کرد."
        if reason:
            warn_msg += f"\n📝 دلیل: {reason}"
        
        # اگر اخطارها به ۳ رسید، کاربر بن شود
        if warnings >= 3:
            try:
                bot.ban_chat_member(group_id, user_id)
                bot.reply_to(message, f"🚫 کاربر به دلیل دریافت ۳ اخطار بن شد!")
                # پاک کردن اخطارهای کاربر
                c.execute("DELETE FROM user_warnings WHERE user_id=? AND group_id=?", (user_id, group_id))
                conn.commit()
            except:
                bot.reply_to(message, "❌ خطا در بن کردن کاربر!")
        else:
            bot.reply_to(message, warn_msg)

@bot.message_handler(commands=['warnings'])
def show_warnings(message):
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        group_id = message.chat.id
        
        c.execute("SELECT warnings FROM user_warnings WHERE user_id=? AND group_id=?", (user_id, group_id))
        result = c.fetchone()
        
        if result:
            bot.reply_to(message, f"⚠️ این کاربر {result[0]}/3 اخطار دارد.")
        else:
            bot.reply_to(message, "✅ این کاربر اخطاری ندارد.")

# ================ مدیریت فیلتر کلمات ================

@bot.message_handler(commands=['addfilter'])
def add_filtered_word(message):
    if not is_admin(message):
        bot.reply_to(message, "⛔️ این دستور فقط برای ادمین‌هاست!")
        return
    
    group_id = message.chat.id
    text = message.text.replace('/addfilter', '').strip()
    
    if not text:
        bot.reply_to(message, "❌ لطفا کلمه مورد نظر را وارد کنید!\nمثال: /addfilter کلمه_ممنوعه warning")
        return
    
    # جدا کردن کلمه و severity
    parts = text.split()
    word = parts[0].lower()
    severity = 'warning'  # پیش‌فرض
    
    if len(parts) > 1 and parts[1] in ['warning', 'ban']:
        severity = parts[1]
    
    try:
        c.execute("INSERT INTO filtered_words (group_id, word, severity) VALUES (?, ?, ?)",
                  (group_id, word, severity))
        conn.commit()
        
        severity_text = "اخطار" if severity == 'warning' else "بن فوری"
        bot.reply_to(message, f"✅ کلمه '{word}' با سطح {severity_text} به لیست فیلتر اضافه شد.")
    except sqlite3.IntegrityError:
        bot.reply_to(message, f"❌ کلمه '{word}' قبلاً در لیست فیلتر وجود دارد!")

@bot.message_handler(commands=['removefilter'])
def remove_filtered_word(message):
    if not is_admin(message):
        bot.reply_to(message, "⛔️ این دستور فقط برای ادمین‌هاست!")
        return
    
    group_id = message.chat.id
    word = message.text.replace('/removefilter', '').strip().lower()
    
    if not word:
        bot.reply_to(message, "❌ لطفا کلمه مورد نظر را وارد کنید!")
        return
    
    c.execute("DELETE FROM filtered_words WHERE group_id=? AND word=?", (group_id, word))
    conn.commit()
    
    if c.rowcount > 0:
        bot.reply_to(message, f"✅ کلمه '{word}' از لیست فیلتر حذف شد.")
    else:
        bot.reply_to(message, f"❌ کلمه '{word}' در لیست فیلتر وجود ندارد!")

@bot.message_handler(commands=['listfilters'])
def list_filtered_words(message):
    if not is_admin(message):
        bot.reply_to(message, "⛔️ این دستور فقط برای ادمین‌هاست!")
        return
    
    group_id = message.chat.id
    c.execute("SELECT word, severity FROM filtered_words WHERE group_id=? ORDER BY word", (group_id,))
    words = c.fetchall()
    
    if not words:
        bot.reply_to(message, "📝 لیست کلمات فیلتر شده خالی است.")
        return
    
    word_list = "🔤 **لیست کلمات فیلتر شده:**\n\n"
    for word, severity in words:
        emoji = "⚠️" if severity == 'warning' else "🚫"
        severity_text = "اخطار" if severity == 'warning' else "بن فوری"
        word_list += f"{emoji} {word} - {severity_text}\n"
    
    word_list += f"\n📊 تعداد کل: {len(words)} کلمه"
    bot.reply_to(message, word_list, parse_mode="Markdown")

@bot.message_handler(commands=['clearfilters'])
def clear_filtered_words(message):
    if not is_admin(message):
        bot.reply_to(message, "⛔️ این دستور فقط برای ادمین‌هاست!")
        return
    
    group_id = message.chat.id
    c.execute("DELETE FROM filtered_words WHERE group_id=?", (group_id,))
    conn.commit()
    
    bot.reply_to(message, f"✅ همه کلمات فیلتر شده پاک شدند. ({c.rowcount} کلمه)")

def check_filtered_words(message):
    """بررسی وجود کلمات فیلتر شده در پیام"""
    if not message.text or is_admin(message):
        return None
    
    group_id = message.chat.id
    text = message.text.lower()
    
    # دریافت لیست کلمات فیلتر شده گروه
    c.execute("SELECT word, severity FROM filtered_words WHERE group_id=?", (group_id,))
    filtered_words = c.fetchall()
    
    for word, severity in filtered_words:
        # بررسی وجود کلمه در متن (به صورت کلمه کامل)
        pattern = r'\b' + re.escape(word) + r'\b'
        if re.search(pattern, text, re.IGNORECASE):
            return {'word': word, 'severity': severity}
    
    return None

# ================ تنظیمات ضد اسپم و لینک ================

@bot.message_handler(commands=['antispam'])
def toggle_antispam(message):
    if not is_admin(message):
        bot.reply_to(message, "⛔️ این دستور فقط برای ادمین‌هاست!")
        return
    
    status = message.text.replace('/antispam', '').strip().lower()
    if status not in ['on', 'off']:
        bot.reply_to(message, "❌ لطفا on یا off را وارد کنید!")
        return
    
    group_id = message.chat.id
    
    # دریافت تنظیمات فعلی
    c.execute("SELECT anti_spam FROM group_settings WHERE group_id=?", (group_id,))
    result = c.fetchone()
    
    value = 1 if status == 'on' else 0
    
    if result:
        c.execute("UPDATE group_settings SET anti_spam=? WHERE group_id=?", (value, group_id))
    else:
        c.execute("INSERT INTO group_settings (group_id, anti_spam) VALUES (?, ?)", (group_id, value))
    
    conn.commit()
    bot.reply_to(message, f"✅ ضد اسپم {status} شد.")

@bot.message_handler(commands=['antilink'])
def toggle_antilink(message):
    if not is_admin(message):
        bot.reply_to(message, "⛔️ این دستور فقط برای ادمین‌هاست!")
        return
    
    status = message.text.replace('/antilink', '').strip().lower()
    if status not in ['on', 'off']:
        bot.reply_to(message, "❌ لطفا on یا off را وارد کنید!")
        return
    
    group_id = message.chat.id
    
    # دریافت تنظیمات فعلی
    c.execute("SELECT anti_link FROM group_settings WHERE group_id=?", (group_id,))
    result = c.fetchone()
    
    value = 1 if status == 'on' else 0
    
    if result:
        c.execute("UPDATE group_settings SET anti_link=? WHERE group_id=?", (value, group_id))
    else:
        c.execute("INSERT INTO group_settings (group_id, anti_link) VALUES (?, ?)", (group_id, value))
    
    conn.commit()
    bot.reply_to(message, f"✅ ضد لینک {status} شد.")

@bot.message_handler(func=lambda m: True)
def check_messages(message):
    # نادیده گرفتن پیام‌های ادمین
    if is_admin(message):
        return
    
    group_id = message.chat.id
    user_id = message.from_user.id
    
    # بررسی کلمات فیلتر شده
    filtered = check_filtered_words(message)
    if filtered:
        delete_and_handle_filtered(message, filtered['word'], filtered['severity'])
        return
    
    # دریافت تنظیمات گروه
    c.execute("SELECT anti_spam, anti_link FROM group_settings WHERE group_id=?", (group_id,))
    settings = c.fetchone()
    
    if settings:
        anti_spam, anti_link = settings
        
        # بررسی اسپم
        if anti_spam and anti_spam == 1:
            if check_spam(message):
                delete_and_warn(message, "اسپم")
                return
        
        # بررسی لینک
        if anti_link and anti_link == 1:
            if message.text and has_link(message.text):
                delete_and_warn(message, "ارسال لینک")
                return

def check_spam(message):
    user_id = message.from_user.id
    current_time = time.time()
    
    if user_id not in user_messages:
        user_messages[user_id] = []
    
    # پاک کردن پیام‌های قدیمی (بیشتر از ۵ ثانیه)
    user_messages[user_id] = [t for t in user_messages[user_id] if current_time - t < 5]
    user_messages[user_id].append(current_time)
    
    # اگر بیش از ۳ پیام در ۵ ثانیه باشد
    return len(user_messages[user_id]) > 3

def has_link(text):
    if not text:
        return False
    # الگوی ساده برای تشخیص لینک
    link_pattern = r'(https?://|www\.)[^\s]+'
    return bool(re.search(link_pattern, text, re.IGNORECASE))

def delete_and_handle_filtered(message, word, severity):
    try:
        bot.delete_message(message.chat.id, message.message_id)
        
        if severity == 'ban':
            # بن فوری کاربر
            try:
                bot.ban_chat_member(message.chat.id, message.from_user.id)
                bot.send_message(message.chat.id, 
                               f"🚫 کاربر {message.from_user.first_name} به دلیل استفاده از کلمه ممنوعه '{word}' بن شد.")
            except:
                bot.reply_to(message, f"❌ کلمه ممنوعه '{word}' شناسایی شد. خطا در بن کاربر!")
        else:
            # اخطار به کاربر
            bot.reply_to(message, f"⚠️ کاربر {message.from_user.first_name}، لطفا از کلمه ممنوعه '{word}' استفاده نکنید!")
            warn_user_auto(message)
    except:
        pass

def delete_and_warn(message, reason):
    try:
        bot.delete_message(message.chat.id, message.message_id)
        bot.reply_to(message, f"❌ پیام شما به دلیل {reason} حذف شد.")
        
        # اضافه کردن اخطار
        warn_user_auto(message)
    except:
        pass

def warn_user_auto(message):
    user_id = message.from_user.id
    group_id = message.chat.id
    
    c.execute("SELECT warnings FROM user_warnings WHERE user_id=? AND group_id=?", (user_id, group_id))
    result = c.fetchone()
    
    if result:
        warnings = result[0] + 1
        c.execute("UPDATE user_warnings SET warnings=? WHERE user_id=? AND group_id=?", (warnings, user_id, group_id))
    else:
        warnings = 1
        c.execute("INSERT INTO user_warnings VALUES (?, ?, ?)", (user_id, group_id, warnings))
    
    conn.commit()
    
    if warnings >= 3:
        try:
            bot.ban_chat_member(group_id, user_id)
            bot.send_message(group_id, f"🚫 کاربر {message.from_user.first_name} به دلیل دریافت ۳ اخطار بن شد.")
            c.execute("DELETE FROM user_warnings WHERE user_id=? AND group_id=?", (user_id, group_id))
            conn.commit()
        except:
            pass

# ================ خوش‌آمدگویی و خداحافظی ================

@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(message):
    group_id = message.chat.id
    c.execute("SELECT welcome_message FROM group_settings WHERE group_id=?", (group_id,))
    result = c.fetchone()
    
    if result and result[0]:
        welcome = result[0]
    else:
        welcome = "خوش آمدید {name} به گروه! 🎉"
    
    for member in message.new_chat_members:
        if member.id == bot.get_me().id:
            bot.reply_to(message, "🙏 ممنون از اضافه کردن من! برای مشاهده دستورات /help را بزنید.")
        else:
            welcome_text = welcome.replace("{name}", member.first_name)
            bot.reply_to(message, welcome_text)

@bot.message_handler(content_types=['left_chat_member'])
def goodbye_member(message):
    group_id = message.chat.id
    c.execute("SELECT goodbye_message FROM group_settings WHERE group_id=?", (group_id,))
    result = c.fetchone()
    
    if result and result[0]:
        goodbye = result[0]
    else:
        goodbye = "خداحافظ {name}! 👋"
    
    member = message.left_chat_member
    if member.id != bot.get_me().id:
        goodbye_text = goodbye.replace("{name}", member.first_name)
        bot.reply_to(message, goodbye_text)

# ================ تنظیمات ================

@bot.message_handler(commands=['setwelcome'])
def set_welcome(message):
    if not is_admin(message):
        bot.reply_to(message, "⛔️ این دستور فقط برای ادمین‌هاست!")
        return
    
    welcome_text = message.text.replace('/setwelcome', '').strip()
    if not welcome_text:
        bot.reply_to(message, "❌ لطفا متن خوش‌آمدگویی را وارد کنید!")
        return
    
    group_id = message.chat.id
    
    # بررسی وجود تنظیمات قبلی
    c.execute("SELECT * FROM group_settings WHERE group_id=?", (group_id,))
    result = c.fetchone()
    
    if result:
        c.execute("UPDATE group_settings SET welcome_message=? WHERE group_id=?", (welcome_text, group_id))
    else:
        c.execute("INSERT INTO group_settings (group_id, welcome_message) VALUES (?, ?)", (group_id, welcome_text))
    
    conn.commit()
    bot.reply_to(message, "✅ پیام خوش‌آمدگویی تنظیم شد.")

@bot.message_handler(commands=['setgoodbye'])
def set_goodbye(message):
    if not is_admin(message):
        bot.reply_to(message, "⛔️ این دستور فقط برای ادمین‌هاست!")
        return
    
    goodbye_text = message.text.replace('/setgoodbye', '').strip()
    if not goodbye_text:
        bot.reply_to(message, "❌ لطفا متن خداحافظی را وارد کنید!")
        return
    
    group_id = message.chat.id
    
    # بررسی وجود تنظیمات قبلی
    c.execute("SELECT * FROM group_settings WHERE group_id=?", (group_id,))
    result = c.fetchone()
    
    if result:
        c.execute("UPDATE group_settings SET goodbye_message=? WHERE group_id=?", (goodbye_text, group_id))
    else:
        c.execute("INSERT INTO group_settings (group_id, goodbye_message) VALUES (?, ?)", (group_id, goodbye_text))
    
    conn.commit()
    bot.reply_to(message, "✅ پیام خداحافظی تنظیم شد.")

# ================ آمار ================

@bot.message_handler(commands=['stats'])
def group_stats(message):
    chat = message.chat
    try:
        admins = bot.get_chat_administrators(chat.id)
        members = bot.get_chat_members_count(chat.id)
        
        # آمار کلمات فیلتر شده
        c.execute("SELECT COUNT(*) FROM filtered_words WHERE group_id=?", (chat.id,))
        filtered_count = c.fetchone()[0]
        
        # آمار کاربران اخطاردار
        c.execute("SELECT COUNT(*) FROM user_warnings WHERE group_id=?", (chat.id,))
        warned_users = c.fetchone()[0]
        
        stats_text = f"""
📊 **آمار گروه**
👥 نام گروه: {chat.title}
📈 تعداد اعضا: {members}
👑 تعداد ادمین‌ها: {len(admins)}
🔤 کلمات فیلتر شده: {filtered_count}
⚠️ کاربران اخطاردار: {warned_users}
🆔 آیدی گروه: {chat.id}
        """
        bot.reply_to(message, stats_text, parse_mode="Markdown")
    except:
        bot.reply_to(message, "❌ خطا در دریافت آمار!")

@bot.message_handler(commands=['admins'])
def list_admins(message):
    try:
        admins = bot.get_chat_administrators(message.chat.id)
        admin_list = "👑 **لیست ادمین‌ها:**\n\n"
        
        for admin in admins:
            user = admin.user
            role = "مدیر" if admin.status == 'creator' else "ادمین"
            admin_list += f"• {user.first_name} - {role}\n"
        
        bot.reply_to(message, admin_list, parse_mode="Markdown")
    except:
        bot.reply_to(message, "❌ خطا در دریافت لیست ادمین‌ها!")

@bot.message_handler(commands=['about'])
def about_bot(message):
    about_text = """
🤖 **ربات مدیریت گروه**
نسخه: 2.0
توسعه داده شده با پایتون

✅ **قابلیت‌ها:**
• مدیریت کاربران (بن، آنبن، اخراج، سکوت)
• سیستم اخطار هوشمند
• ضد اسپم و ضد لینک
• **فیلتر کلمات ممنوعه** (با قابلیت اخطار یا بن فوری)
• پیام خوش‌آمدگویی و خداحافظی
• آمار گروه

برای اطلاعات بیشتر از /help استفاده کنید.
    """
    bot.reply_to(message, about_text, parse_mode="Markdown")

# ================ حذف پیام ================

@bot.message_handler(commands=['del'])
def delete_message(message):
    if not is_admin(message):
        bot.reply_to(message, "⛔️ این دستور فقط برای ادمین‌هاست!")
        return
    
    if message.reply_to_message:
        try:
            bot.delete_message(message.chat.id, message.reply_to_message.message_id)
            bot.delete_message(message.chat.id, message.message_id)
        except:
            bot.reply_to(message, "❌ خطا در حذف پیام!")

# ================ سنجاق پیام ================

@bot.message_handler(commands=['pin'])
def pin_message(message):
    if not is_admin(message):
        bot.reply_to(message, "⛔️ این دستور فقط برای ادمین‌هاست!")
        return
    
    if message.reply_to_message:
        try:
            bot.pin_chat_message(message.chat.id, message.reply_to_message.message_id)
            bot.reply_to(message, "✅ پیام سنجاق شد.")
        except:
            bot.reply_to(message, "❌ خطا در سنجاق پیام!")

@bot.message_handler(commands=['unpin'])
def unpin_message(message):
    if not is_admin(message):
        bot.reply_to(message, "⛔️ این دستور فقط برای ادمین‌هاست!")
        return
    
    try:
        bot.unpin_chat_message(message.chat.id)
        bot.reply_to(message, "✅ پیام از سنجاق خارج شد.")
    except:
        bot.reply_to(message, "❌ خطا در لغو سنجاق!")

# ================ تابع کمکی بررسی ادمین ================

def is_admin(message):
    try:
        user_status = bot.get_chat_member(message.chat.id, message.from_user.id).status
        return user_status in ['administrator', 'creator']
    except:
        return False

# ================ اجرای ربات ================

if __name__ == "__main__":
    print("🤖 ربات مدیریت گروه با موفقیت اجرا شد!")
    print("✅ قابلیت فیلتر کلمات فعال است.")
    bot.infinity_polling()