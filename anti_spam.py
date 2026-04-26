from telegram import Update, Message, InlineKeyboardMarkup, InlineKeyboardButton, User, LabeledPrice, SuccessfulPayment, InputMediaPhoto, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton, KeyboardButtonRequestUsers, LinkPreviewOptions, ChatMemberUpdated, ChatMember, Chat, InputFile, WebAppInfo
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, ExtBot, CallbackQueryHandler, PreCheckoutQueryHandler, ShippingQueryHandler, ChatMemberHandler
import time

def itime():
    return int(time.time())


class AntiSpam:
    users: dict[int, dict[str, int]] = {}

    def spam_protect_command(self, func):
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_id = update.effective_user
            if (user_id is None):
                return
            user_id = user_id.id
            ctime = itime()

            tmp = self.users.get(user_id, {"penalty": 0, "last_active": itime(), "warned": False})
            delta = ctime - tmp["last_active"]
            
            if (delta < 2):
                tmp["penalty"] += 2
            elif (delta > 60):
                tmp["penalty"] = 0
            elif (delta > 10):
                tmp["penalty"] = max(0, tmp["penalty"] - 4)
            elif (delta < 5):
                tmp["penalty"] = max(0, tmp["penalty"] - 1)
            else:
                tmp["penalty"] = max(0, tmp["penalty"] - 2)

            tmp['last_active'] = ctime
            if (tmp["penalty"] <= 6):
                await func(update, context, *args, **kwargs)
                tmp["warned"] = False
            else:
                if (not tmp["warned"]):
                    await update.effective_message.reply_text("Зафиксирован спам, оправка сообщений будет ограничена для вас!")
                    tmp["warned"] = True
            self.users[user_id] = tmp
    
        return wrapper

