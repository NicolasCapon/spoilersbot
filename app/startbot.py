import config
import sys
import traceback
from telegram import ParseMode
from telegram.ext import Updater, CommandHandler
from telegram.utils.helpers import mention_html
from spoiler_controller import SpoilerController


def main():
    # Create the EventHandler and pass it your bot's token.
    updater = Updater(config.telegram_token, use_context=True)

    # log all errors
    updater.dispatcher.add_error_handler(error)

    # Add test handler to see if bot still up
    updater.dispatcher.add_handler(CommandHandler("test", test))

    # Start the Bot
    updater.start_polling()
    SpoilerController(updater=updater)
    config.bot_logger.info("Spoiler Bot Started")
    updater.bot.send_message(chat_id=config.admin_id,
                             text="Bot started")

    # Run the bot until the you presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


# this is a general error handler function. If you need more information about specific type of update, add it to the
# payload in the respective if clause
def error(update, context):
    if not update:
        return
    # add all the dev user_ids in this list. You can also add ids of channels or groups.
    devs = [config.admin_id]
    # we want to notify the user of this problem. This will always work, but not notify users if the update is an
    # callback or inline query, or a poll update. In case you want this, keep in mind that sending the message
    # could fail
    if update.effective_message:
        text = "Hey. I'm sorry to inform you that an error happened while I tried to handle your update. " \
               "My developer(s) will be notified."
        update.effective_message.reply_text(text)
    # This traceback is created with accessing the traceback object from the sys.exc_info, which is returned as the
    # third value of the returned tuple. Then we use the traceback.format_tb to get the traceback as a string, which
    # for a weird reason separates the line breaks in a list, but keeps the linebreaks itself. So just joining an
    # empty string works fine.
    trace = "".join(traceback.format_tb(sys.exc_info()[2]))
    # lets try to get as much information from the telegram update as possible
    payload = ""
    # normally, we always have an user. If not, its either a channel or a poll update.
    if update.effective_user:
        payload += f' with the user {mention_html(update.effective_user.id, update.effective_user.first_name)}'
    # there are more situations when you don't get a chat
    if update.effective_chat:
        payload += f' within the chat <i>{update.effective_chat.title}</i>'
        if update.effective_chat.username:
            payload += f' (@{update.effective_chat.username})'
    # but only one where you have an empty payload by now: A poll (buuuh)
    if update.poll:
        payload += f' with the poll id {update.poll.id}.'
    # lets put this in a "well" formatted text
    text = f"Hey.\n The error <code>{context.error}</code> happened{payload}. The full traceback:\n\n<code>{trace}" \
           f"</code>"
    # and send it to the dev(s)
    for dev_id in devs:
        context.bot.send_message(dev_id, text, parse_mode=ParseMode.HTML)
    # we raise the error again, so the logger module catches it. If you don't use the logger module, use it.
    raise


def test(update, context):
    text = "I'm still up"
    update.message.reply_text(text, quote=True)


if __name__ == '__main__':
    main()
