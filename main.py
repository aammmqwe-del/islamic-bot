import sqlite3
import random
import requests
import os
from datetime import datetime, timedelta
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# --- البيانات الأساسية المحمية ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = 844192857

# إنشاء مجلدات حفظ الصور محلياً لحمايتها من الحذف عند إغلاق الجهاز
os.makedirs("friday_images", exist_ok=True)
os.makedirs("dua_images", exist_ok=True)

# موسوعة الأذكار الأساسية
local_nawaf_api = [
    {"text": "أستغفر الله العظيم وأتوب إليه"},
    {"text": "سبحان الله وبحمده، سبحان الله العظيم"},
    {"text": "لا إله إلا الله وحده لا شريك له، له الملك وله الحمد وهو على كل شيء قدير"},
    {"text": "اللهم صلّ وسلم على نبينا محمد"},
    {"text": "لا حول ولا قوة إلا بالله العلي العظيم"},
    {"text": "يا حي يا قيوم برحمتك أستغيث، أصلِح لي شأني كله ولا تكلني إلى نفسي طرفة عين"},
    {"text": "سُبْحَانَ اللهِ وَبِحَمْدِهِ: عَدَدَ خَلْقِهِ، وَرِضَا نَفْسِهِ، وَزِنةَ عَرْشِهِ، وَمِدَادَ كَلِمَاتِهِ"},
    {"text": "اللهم إنك عفو تحب العفو فاعفُ عني"},
    {"text": "لا إله إلا أنت سبحانك إني كنت من الظالمين"}
]

# --- إعداد قاعدة البيانات الشاملة ---
def init_db():
    conn = sqlite3.connect("islamic_bot.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            interval_hours INTEGER DEFAULT 2,
            latitude REAL,
            longitude REAL,
            last_sent TEXT,
            last_prayer_notified TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT,
            category TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sent_images_history (
            user_id INTEGER,
            image_id INTEGER,
            category TEXT,
            PRIMARY KEY (user_id, image_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS custom_azkar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_all_azkar():
    combined_list = list(local_nawaf_api)
    try:
        conn = sqlite3.connect("islamic_bot.db")
        cursor = conn.cursor()
        cursor.execute("SELECT text FROM custom_azkar")
        for row in cursor.fetchall():
            combined_list.append({"text": row[0]})
        conn.close()
    except:
        pass
    return combined_list

# --- القائمة الرئيسية ---
async def send_main_menu(update: Update, text: str):
    buttons = [
        [KeyboardButton("⚙️ ضبط وقت التذكير"), KeyboardButton("🕌 مواقيت الصلاة")],
        [KeyboardButton("📿 ذكرني الآن (فوري)"), KeyboardButton("📖 آية وعبرة")],
        [KeyboardButton("📸 صور يوم الجمعة"), KeyboardButton("🙌 صور أدعية")]
    ]
    reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    conn = sqlite3.connect("islamic_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()
    await send_main_menu(update, "🌿 **مرحباً بك في بوت التذكير الشامل ومواقيت الصلاة العالمية** 🌿")

# --- معالجة حفظ الموقع الجغرافي ---
async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    lat = update.message.location.latitude
    lon = update.message.location.longitude
    conn = sqlite3.connect("islamic_bot.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET latitude = ?, longitude = ? WHERE user_id = ?", (lat, lon, user_id))
    conn.commit()
    conn.close()
    await update.message.reply_text("✅ تم حفظ موقعك بنجاح! سيقوم البوت الآن بتنبيهك قبل كل صلاة بـ 5 دقائق تلقائياً.")

# --- استقبال رسائل الكيبورد والهاشتاقات النصية للأدمن ---
async def handle_text_and_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text if update.message.text else ""
    user_id = update.message.from_user.id
    
    # [1] أدمن: إضافة ذكر جديد عبر هاشتاق #ذكر
    if user_id == ADMIN_ID and user_text.startswith("#ذكر"):
        zikr_content = user_text.replace("#ذكر", "").strip()
        if zikr_content:
            conn = sqlite3.connect("islamic_bot.db")
            cursor = conn.cursor()
            cursor.execute("INSERT INTO custom_azkar (text) VALUES (?)", (zikr_content,))
            conn.commit()
            conn.close()
            await update.message.reply_text(f"✅ تم إضافة الذكر الجديد للموسوعة وب بساطة:\n`{zikr_content}`")
        return

    # [2] أدمن: إذاعة نصية فورية لجميع المشتركين عبر هاشتاق #الان
    if user_id == ADMIN_ID and user_text.startswith("#الان"):
        broadcast_msg = user_text.replace("#الان", "").strip()
        if broadcast_msg:
            conn = sqlite3.connect("islamic_bot.db")
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users")
            all_users = cursor.fetchall()
            conn.close()
            
            success_count = 0
            for u in all_users:
                try:
                    await context.bot.send_message(chat_id=u[0], text=f"📢 **تنبيه عام من الإدارة:**\n\n{broadcast_msg}")
                    success_count += 1
                except:
                    continue
            await update.message.reply_text(f"🚀 تم إرسال الإذاعة الجماعية بنجاح إلى ({success_count}) مشترك!")
        return

    # الأزرار العادية للمستخدمين
    if user_text == "📿 ذكرني الآن (فوري)":
        current_azkar = get_all_azkar()
        chosen = random.choice(current_azkar)
        await update.message.reply_text(f"📿 **ذكر مخصص لك الآن:**\n\n🕊️ `{chosen['text']}`", parse_mode="Markdown")

    elif user_text == "📖 آية وعبرة":
        random_ayah = random.randint(1, 6236)
        try:
            res = requests.get(f"https://api.alquran.cloud/v1/ayah/{random_ayah}/ar.jalaleen", timeout=5).json()
            data = res['data']
            await update.message.reply_text(f"📖 **من نفحات القرآن:**\n\n🕊️ « *{data['text']}* »\n\nسورة: **{data['surah']['name']}** | آية: **{data['numberInSurah']}**", parse_mode="Markdown")
        except:
            await update.message.reply_text("❌ لا إله إلا أنت سبحانك إني كنت من الظالمين.")

    elif user_text == "🕌 مواقيت الصلاة":
        conn = sqlite3.connect("islamic_bot.db")
        cursor = conn.cursor()
        cursor.execute("SELECT latitude, longitude FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row and row[0] and row[1]:
            lat, lon = row[0], row[1]
            try:
                url = f"https://api.aladhan.com/v1/timings?latitude={lat}&longitude={lon}&method=4"
                res = requests.get(url, timeout=5).json()
                t = res['data']['timings']
                
                def convert_time(t_str):
                    return datetime.strptime(t_str, "%H:%M").strftime("%I:%M %p").replace("AM", "صباحاً").replace("PM", "مساءً")
                
                msg = (
                    f"🕌 **مواقيت الصلاة لموقعك الحالي:**\n\n"
                    f"☀️ **الفجر:** {convert_time(t['Fajr'])}\n"
                    f"🌅 **الشروق:** {convert_time(t['Sunrise'])}\n"
                    f"☀️ **الظهر:** {convert_time(t['Dhuhr'])}\n"
                    f"⛅ **العصر:** {convert_time(t['Asr'])}\n"
                    f"🌌 **المغرب:** {convert_time(t['Maghrib'])}\n"
                    f"🌃 **العشاء:** {convert_time(t['Isha'])}"
                )
                await update.message.reply_text(msg, parse_mode="Markdown")
            except:
                await update.message.reply_text("❌ حدث خطأ أثناء جلب المواقيت.")
        else:
            btn = [[KeyboardButton("📍 مشاركة الموقع الجغرافي", request_location=True)]]
            await update.message.reply_text("⚠️ يرجى الضغط على الزر أدناه لإرسال موقعك وحساب المواقيت بدقة لتفعيل تنبيهات الـ 5 دقائق التلقائية:", reply_markup=ReplyKeyboardMarkup(btn, resize_keyboard=True, one_time_keyboard=True))

    elif user_text == "⚙️ ضبط وقت التذكير":
        keyboard = [
            [InlineKeyboardButton("ساعة ⏰", callback_data="set_1"), InlineKeyboardButton("ساعتين ⏳", callback_data="set_2"), InlineKeyboardButton("3 ساعات 🕒", callback_data="set_3")],
            [InlineKeyboardButton("4 ساعات ⏱️", callback_data="set_4"), InlineKeyboardButton("6 ساعات 🪵", callback_data="set_6"), InlineKeyboardButton("8 ساعات 🌌", callback_data="set_8")],
            [InlineKeyboardButton("12 ساعة 🌓", callback_data="set_12"), InlineKeyboardButton("24 ساعة 📅", callback_data="set_24")],
            [InlineKeyboardButton("إيقاف التذكير الدوري 🛑", callback_data="set_0")]
        ]
        await update.message.reply_text("⚙️ **لوحة التحكم في وقت التذكير الدوري والآلي:**\n\nاختر كم تبي البوت يذكرك بالخلفية تلقائياً:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif user_text in ["📸 صور يوم الجمعة", "🙌 صور أدعية"]:
        category = "friday" if "الجمعة" in user_text else "dua"
        conn = sqlite3.connect("islamic_bot.db")
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, file_path FROM images 
            WHERE category = ? AND id NOT IN (
                SELECT image_id FROM sent_images_history WHERE user_id = ? AND category = ?
            )
        ''', (category, user_id, category))
        available = cursor.fetchall()
        
        if not available:
            cursor.execute("DELETE FROM sent_images_history WHERE user_id = ? AND category = ?", (user_id, category))
            conn.commit()
            cursor.execute("SELECT id, file_path FROM images WHERE category = ?", (category,))
            available = cursor.fetchall()
            
        if available:
            img_id, file_path = random.choice(available)
            try:
                with open(file_path, "rb") as photo_file:
                    await update.message.reply_photo(photo=photo_file, caption="✨ مأجور ومشكور.. جُعلت في ميزان حسناتك.")
                cursor.execute("INSERT OR IGNORE INTO sent_images_history (user_id, image_id, category) VALUES (?, ?, ?)", (user_id, img_id, category))
                conn.commit()
            except:
                await update.message.reply_text("❌ تعذر فتح أو إرسال ملف الصورة محلياً.")
        else:
            await update.message.reply_text("📦 لا توجد صور متوفرة في هذا القسم حالياً، ارفعها بهاشتاق الأدمن أولاً.")
        conn.close()

# --- معالجة رفع الصور وميزة الـ Broadcast الصوري من الأدمن ---
async def handle_admin_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    caption = update.message.caption if update.message.caption else ""
    
    if user_id != ADMIN_ID or not caption.startswith("#"):
        return

    # [1] أدمن: إذاعة صور جماعية فورية لكل المشتركين عبر هاشتاق #الان
    if caption.startswith("#الان"):
        msg_content = caption.replace("#الان", "").strip()
        photo_file = await update.message.photo[-1].get_file()
        local_path = "temp_broadcast.jpg"
        await photo_file.download_to_drive(local_path)
        
        conn = sqlite3.connect("islamic_bot.db")
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        all_users = cursor.fetchall()
        conn.close()
        
        success_count = 0
        for u in all_users:
            try:
                with open(local_path, "rb") as f:
                    await context.bot.send_photo(chat_id=u[0], photo=f, caption=f"📢 **إعلان عام من الإدارة:**\n\n{msg_content}" if msg_content else None)
                success_count += 1
            except:
                continue
        if os.path.exists(local_path):
            os.remove(local_path)
        await update.message.reply_text(f"📸 تم إذاعة الصورة بنجاح إلى ({success_count}) مشترك غصب!")
        return

    # [2] أدمن: حفظ الصور محلياً بالأقسام لمنع حذفها عند إطفاء الجهاز
    category = ""
    folder = ""
    if "#جمعة" in caption:
        category = "friday"
        folder = "friday_images"
    elif "#دعاء" in caption:
        category = "dua"
        folder = "dua_images"
        
    if category:
        photo_file = await update.message.photo[-1].get_file()
        file_name = f"{folder}/{update.message.photo[-1].file_unique_id}.jpg"
        await photo_file.download_to_drive(file_name)
        
        conn = sqlite3.connect("islamic_bot.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO images (file_path, category) VALUES (?, ?)", (file_name, category))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ تم حفظ الصورة محلياً بمجلد {folder} بأمان وبدون تكرار نهائياً!")

# --- معالجة أزرار التوقيت الشفافة ---
async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if query.data.startswith("set_"):
        hours = int(query.data.split("_")[1])
        conn = sqlite3.connect("islamic_bot.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET interval_hours = ?, last_sent = NULL WHERE user_id = ?", (hours, user_id))
        conn.commit()
        conn.close()
        msg = "🛑 تم إيقاف التذكير الدوري تلقائياً." if hours == 0 else f"✅ أبشر! تم ضبط التذكير التلقائي بالخلفية كل **{hours} ساعة** بنجاح."
        await query.edit_message_text(msg)

# --- ماكينة الخلفية الدقيقة (تنبيه الصلاة بـ 5 دقائق + التذكير الدوري بالأذكار) ---
async def auto_reminder_job(context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect("islamic_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, interval_hours, last_sent, latitude, longitude, last_prayer_notified FROM users")
    all_users = cursor.fetchall()
    conn.close()
    
    now = datetime.now()
    current_azkar = get_all_azkar()
    
    for u in all_users:
        user_id, interval, last_sent, lat, lon, last_prayer_notified = u
        
        # [1] التنبيه قبل الصلاة بـ 5 دقائق بالضبط عالمياً
        if lat and lon:
            try:
                url = f"https://api.aladhan.com/v1/timings?latitude={lat}&longitude={lon}&method=4"
                res = requests.get(url, timeout=5).json()
                timings = res['data']['timings']
                
                prayers = ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha']
                for p in prayers:
                    p_time_str = timings[p]
                    p_time = datetime.strptime(f"{now.strftime('%Y-%m-%d')} {p_time_str}", "%Y-%m-%d %H:%M")
                    
                    time_diff = p_time - now
                    # الفحص البرمجي قبل الأذان بـ 5 دقائق
                    if timedelta(minutes=4) <= time_diff <= timedelta(minutes=6):
                        p_key = f"{p}_{now.strftime('%Y-%m-%d')}"
                        if last_prayer_notified != p_key:
                            names = {'Fajr': 'الفجر', 'Dhuhr': 'الظهر', 'Asr': 'العصر', 'Maghrib': 'المغرب', 'Isha': 'العشاء'}
                            await context.bot.send_message(chat_id=user_id, text=f"🔔 **تنبيه وإشعار إيماني عاجل:**\n\nباقي على أذان صلاة **{names[p]}** 5 دقائق فقط.. استعد وتوضأ للصلاة الآن. ✨")
                            
                            conn = sqlite3.connect("islamic_bot.db")
                            cursor = conn.cursor()
                            cursor.execute("UPDATE users SET last_prayer_notified = ? WHERE user_id = ?", (p_key, user_id))
                            conn.commit()
                            conn.close()
            except:
                pass

        # [2] التذكير الدوري التلقائي بالأذكار
        if interval > 0:
            should_send = False
            if not last_sent:
                should_send = True
            else:
                try:
                    last_date = datetime.strptime(last_sent, "%Y-%m-%d %H:%M:%S")
                    if now >= last_date + timedelta(hours=interval):
                        should_send = True
                except:
                    should_send = True
                    
            if should_send:
                try:
                    chosen = random.choice(current_azkar)
                    await context.bot.send_message(chat_id=user_id, text=f"🔔 **تذكيرك الدوري التلقائي:**\n\n🕊️ `{chosen['text']}`")
                    conn = sqlite3.connect("islamic_bot.db")
                    cursor = conn.cursor()
                    cursor.execute("UPDATE users SET last_sent = ? WHERE user_id = ?", (now.strftime("%Y-%m-%d %H:%M:%S"), user_id))
                    conn.commit()
                    conn.close()
                except:
                    continue

# --- تشغيل النظام الاحترافي المكتمل ---
if __name__ == "__main__":
    print("⚡ الموسوعة الكبرى شغالة الآن! أوقات صلاة، تنبيه الـ 5 دقائق، إذاعة #الان، وحفظ محلي للصور من الحذف..")
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.job_queue.run_repeating(auto_reminder_job, interval=60, first=10)
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(MessageHandler(filters.PHOTO, handle_admin_media))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_and_admin))
    app.add_handler(CallbackQueryHandler(handle_callbacks))
    
    app.run_polling(close_loop=False, drop_pending_updates=True)