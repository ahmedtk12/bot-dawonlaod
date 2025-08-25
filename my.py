import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
from telegram.error import BadRequest
import os
import re

TOKEN = "7452949561:AAH6w41AXSg7iP8HB9fKoNEXEKldmeLv2_4"
CHANNEL_USERNAME = "@V_ML0"

SITES = {
    "Instagram": r"(https?://(www\.)?instagram\.com/[^\s]+)",
    "Facebook": r"(https?://(www\.)?facebook\.com/[^\s]+)",
    "X": r"(https?://(www\.)?(twitter|x)\.com/[^\s]+)",
    "TikTok": r"(https?://(www\.)?tiktok\.com/[^\s]+)",
    "YouTube": r"(https?://(www\.)?(youtube\.com|youtu\.be)/[^\s]+)"
}

SELECT_SITE, WAIT_LINK = range(2)

async def is_subscribed(user_id, context: ContextTypes.DEFAULT_TYPE):
    try:
        member = await context.bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ["member", "administrator", "creator"]
    except BadRequest:
        return False

async def send_platform_menu(update, context):
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(site, callback_data=site)] for site in SITES.keys()
    ])
    if hasattr(update, "message") and update.message:
        await update.message.reply_text(
            "اختر المنصة التي تريد التحميل منها:",
            reply_markup=markup
        )
    elif hasattr(update, "callback_query") and update.callback_query:
        await update.callback_query.message.reply_text(
            "اختر المنصة التي تريد التحميل منها:",
            reply_markup=markup
        )
    return SELECT_SITE

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await is_subscribed(user_id, context):
        await update.message.reply_text(
            f"❌ يجب الاشتراك في القناة أولاً: {CHANNEL_USERNAME}\nثم أرسل /start بعد الاشتراك."
        )
        context.user_data.clear()
        return ConversationHandler.END

    return await send_platform_menu(update, context)

async def select_site(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    site = query.data
    context.user_data["site"] = site
    await query.edit_message_text(
        f"أرسل رابط الفيديو الخاص بمنصة {site}:"
    )
    return WAIT_LINK

async def wait_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await is_subscribed(user_id, context):
        await update.message.reply_text(
            f"❌ يجب الاشتراك في القناة أولاً: {CHANNEL_USERNAME}\nثم أرسل /start بعد الاشتراك."
        )
        context.user_data.clear()
        return ConversationHandler.END

    site = context.user_data.get("site")
    pattern = SITES.get(site)
    link = update.message.text.strip()

    # تحقق إذا الرابط يخص منصة أخرى
    for other_site, other_pattern in SITES.items():
        if other_site != site and re.match(other_pattern, link):
            await update.message.reply_text(
                "⚠️ الرابط الذي أرسلته يخص منصة أخرى.\n"
                "يرجى الضغط على /start واختيار المنصة الصحيحة أولاً."
            )
            context.user_data.clear()
            return ConversationHandler.END

    if not re.match(pattern, link):
        await update.message.reply_text(
            f"⚠️ الرابط المرسل لا يخص منصة {site}. الرجاء التأكد من الرابط."
        )
        return WAIT_LINK

    await update.message.reply_text(f"⏳ جاري تحميل الفيديو من {site}...")

    ydl_opts = {
        "format": "best",
        "outtmpl": "downloads/video.%(ext)s"
    }
    os.makedirs("downloads", exist_ok=True)
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(link, download=False)
            # تحقق من مدة الفيديو إذا كان يوتيوب
            if site == "YouTube":
                duration = info_dict.get("duration", 0)
                if duration > 300:
                    await update.message.reply_text("❌ عذراً، فقط الفيديوهات الأقل من 5 دقائق مسموح بها من يوتيوب.")
                    context.user_data.clear()
                    return ConversationHandler.END
            # حمل الفيديو فعلياً
            ydl.download([link])
            file_path = ydl.prepare_filename(info_dict)
        with open(file_path, "rb") as video:
            size = os.path.getsize(file_path)
            if size > 49 * 1024 * 1024:
                await update.message.reply_text("❌ الفيديو أكبر من 50 ميجابايت ولا يمكن إرساله عبر تيليجرام.")
            else:
                await update.message.reply_video(video)
                await update.message.reply_text("تم التحميل بنجاح ✅")
                # أظهر قائمة اختيار المنصة من جديد
                await send_platform_menu(update, context)
                context.user_data.clear()
                return SELECT_SITE
        os.remove(file_path)
    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ أثناء التحميل: {str(e)}")
    context.user_data.clear()
    return ConversationHandler.END

async def force_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await is_subscribed(user_id, context):
        await update.message.reply_text(
            f"❌ يجب الاشتراك في القناة أولاً: {CHANNEL_USERNAME}\nثم أرسل /start بعد الاشتراك."
        )
        context.user_data.clear()
        return ConversationHandler.END
    else:
        return await start(update, context)

def main():
    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_SITE: [CallbackQueryHandler(select_site)],
            WAIT_LINK: [MessageHandler(filters.TEXT & (~filters.COMMAND), wait_link)],
        },
        fallbacks=[MessageHandler(filters.ALL, force_sub)],
        allow_reentry=True,
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("help", start))

    app.run_polling()

if __name__ == "__main__":
    main()
