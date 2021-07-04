import logging
# from os import listdir
# from random import randint
# from numpy import base_repr
import sqlite3
from time import time

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup, InputMedia, InputMediaPhoto, Update
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
    CallbackContext,
    CallbackQueryHandler,
)

# Enable logging
logging.basicConfig(
    filename='bot.log', encoding='utf-8',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)

ROCK, PAPER, SCISSORS = range(2,5)
SYMBOLS = ("", "", u"\u270A\U0001F3FB", u"\U0001F91A\U0001F3FB", u"\u270C\U0001F3FB", "-")

def go_start(update: Update, context: CallbackContext) -> None:
    """Starts command."""
    reply_keyboard = [["Играть!"]]

    update.message.reply_text(
        "Нажмите кнопку Играть!, чтобы начать игру ",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=False, resize_keyboard=True),
    )
def get_unix_datetime():
    return ''

def remove_job_if_exists(name: str, context: CallbackContext) -> bool:
    """Remove job with given name. Returns whether job was removed."""
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True

def run_game(update: Update, context: CallbackContext):
    reply_keyboard = [["Отмена"]]
    conn = sqlite3.connect('game.db')
    
    curs = conn.cursor()
    curs.execute("SELECT * from games WHERE (iduser1 = ? OR iduser2 = ?) AND (state1 < 2 OR state2 < 2)", (update.message.chat.id, update.message.chat.id))
    data = curs.fetchall();

    if len(data) > 0: # пользователь уже в игре, просто игнорируем команду
        #update.callback_query.answer("Вы так то уже в игре")
        # редактируем сообщение о начале новой игры
        userid = update.message.chat.id
        mess_id = update.message.message_id
        update.message.bot.deleteMessage(userid, mess_id)
        msg = update.message.bot.send_message(chat_id=userid, text="Вы уже в игре!")
        m = msg
        # update.message.bot.edit_message_text(chat_id=userid, message_id=mess_id, text="Вы уже в игре")
    else: 
        # пользователь не состоит ни в одной игре - пытаемся найти соперника, готового сыграть. 
        #
        curs.execute("SELECT rowid, * from games WHERE state1 = 0 ORDER BY date LIMIT 1")
        data = curs.fetchall();
        if len(data) > 0: # соперник найден, обновляем запись в БД нашими данными
            
            # здесь надо обязательно удалить job, удаляющую неактивную игру
            #context.
            player1 = data[0][1]
            rowid = data[0][0]
            job_removed = remove_job_if_exists(str(player1) + "_" + str(rowid), context)

            
            keyboard = [
                [
                    InlineKeyboardButton(SYMBOLS[ROCK], callback_data='Rock_' + str(rowid)),
                    InlineKeyboardButton(SYMBOLS[PAPER], callback_data='Paper_' + str(rowid)),
                    InlineKeyboardButton(SYMBOLS[SCISSORS], callback_data='Scissors_' + str(rowid)),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            # отсылка сообщения первому игроку
            msg = update.message.reply_text(
                "Ваш соперник - игрок с номером " + str(data[0][1]) + '\nВы болтаете друг перед другом кулаками, пришло время решить, какой знак вы покажете, когда наступит тот самый момент',
                reply_markup=reply_markup,
            )

            
            userid = data[0][1]
            t = time()
            curs.execute("UPDATE games SET iduser2 = ?, date = ?, state1 = 1, state2 = 1, msg2 = ? WHERE rowid = ?", (update.message.chat.id, t, msg.message_id, rowid))
            conn.commit()
            curs.close()
            conn.close()
            
            # отсылка сообщения второму игроку
            id = update.message.chat.id
            update.message.bot.edit_message_text(chat_id=userid, message_id=data[0][6], text="Ваш соперник - игрок с номером " + str(id), reply_markup=reply_markup,)
            
        else: # Иначе создаём запись новой игры в БД (и ждём, пока кто-нибудь не захочет поиграть)
            msg = update.message.reply_text(
                "Ищем соперника для вас..."
            )
            t = time()
            curs.execute("INSERT INTO games (iduser1, iduser2, date, state1, state2, msg1, msg2) VALUES(?, NULL, ?, 0, 0, ?, NULL)", (update.message.chat.id, t, msg.message_id))
            conn.commit()
            lastrowid = curs.lastrowid
            keyboard = [
                [
                    InlineKeyboardButton("Отмена", callback_data='Cancel_' + str(lastrowid)),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            curs.close()
            conn.close()
            id = update.message.chat.id
            update.message.bot.edit_message_text(chat_id=id, message_id=msg.message_id, text="К сожалению, пока нет желающего сыграть с вами. Подождите немного или нажмите кнопку Отмена\n(по истечении минуты, если никто так и не появится, игра будет отменена автоматически)", reply_markup=reply_markup,)
            # тут запускаем job, чтобы через какое-то время игра отменилась, если никто так и не захочет сыграть
            chat_id = update.message.chat.id
            context.job_queue.run_once(alarm, 60, context = chat_id, name = str(chat_id) + '_' + str(lastrowid))
            
def alarm(context: CallbackContext) -> None:
    """Send the alarm message."""
    job = context.job
    #context.bot.send_message(job.context, text='Beep!')

    msg_num = EndOfTheGame(job.name)

    id = context.job.context
    context.bot.deleteMessage(context.job.context, msg_num)
    reply_keyboard = [["Играть!"]]
    mess = context.bot.send_message(chat_id=id, text="Игра отменена по истечению времени!", reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=False, resize_keyboard=True),)


def Execute(update: Update, context: CallbackContext, action):
    reply_keyboard = [["Играть!"]]
    query = update.callback_query

    query.answer()

    s = update.callback_query.data
    id = update.callback_query.message.chat.id
    ss = s.split('_')
    rowid = int(ss[1])
    conn = sqlite3.connect('game.db')
    
    curs = conn.cursor()
    curs.execute("SELECT * from games WHERE rowid = ? AND iduser1 = ?", (rowid, id))
    data = curs.fetchall();
    if len(data) > 0: # 
        curs.execute("UPDATE games SET state1 = ? WHERE rowid = ?", (action, rowid))
        conn.commit()
    else:
        curs.execute("UPDATE games SET state2 = ? WHERE rowid = ?", (action, rowid))
        conn.commit()

    curs.execute("SELECT * from games WHERE rowid = ? AND state1 > 1 AND state2 > 1", (rowid,))
    data = curs.fetchall();
    if len(data) > 0: # оба игрока сделали свой выбор! Игра окончена, пора выявлять победителя!
        set1 = {'24', '32', '43'}
        set2 = {'23', '34', '42'}
        state1 = data[0][3]
        state2 = data[0][4]
        user1 = data[0][0]
        user2 = data[0][1]
        msg1 = data[0][5]
        msg2 = data[0][6]

        pair = str(state1)+str(state2)
        if state1 == state2: # ничья
            logger.info("Draw!")
            
            query.bot.edit_message_text(chat_id=user1, message_id=msg1, text = SYMBOLS[state1] + " vs " + SYMBOLS[state2] + " В вашем поединке с соперником " + str(user2) + " зафиксирована боевая ничья!")
            query.bot.edit_message_text(chat_id=user2, message_id=msg2, text = SYMBOLS[state1] + " vs " + SYMBOLS[state2] + " В вашем поединке с соперником " + str(user1) + " зафиксирована боевая ничья!")
        else:
            if pair in set1: # победил первый
                query.bot.edit_message_text(chat_id=user1,message_id=msg1, text = SYMBOLS[state1] + " vs " + SYMBOLS[state2] + " Вы победили соперника " + str(user2) + "!")
                query.bot.edit_message_text(chat_id=user2, message_id=msg2, text = SYMBOLS[state1] + " vs " + SYMBOLS[state2] + " Вы проиграли сопернику " + str(user1) + "!")
            else: # победил второй
                query.bot.edit_message_text(chat_id=user2, message_id=msg2, text = SYMBOLS[state1] + " vs " + SYMBOLS[state2] + " Вы победили соперника " + str(user1) + "!")
                query.bot.edit_message_text(chat_id=user1, message_id=msg1, text = SYMBOLS[state1] + " vs " + SYMBOLS[state2] + " Вы проиграли сопернику " + str(user2) + "!")

    curs.close()
    conn.close()


def Rock(update: Update, context: CallbackContext):
    Execute(update, context, ROCK)

def Paper(update: Update, context: CallbackContext):
    Execute(update, context, PAPER)

def Scissors(update: Update, context: CallbackContext):
    Execute(update, context, SCISSORS)

def Cancel(update: Update, context: CallbackContext):
    # если инициатору игры не с кем сразиться, то он может всё отменить
    reply_keyboard = [["Играть!"]]

    s = update.callback_query.data
    query = update.callback_query

    msg_num = EndOfTheGame(s)

    ss = s.split('_')
    rowid = int(ss[1])
#    conn = sqlite3.connect('game.db')
#    curs = conn.cursor()
#    curs.execute("UPDATE games SET state1 = 5, state2 = 5 WHERE rowid = ?", (rowid,))
#    conn.commit()
#    curs.close()
#    conn.close()

    id = update.callback_query.message.chat.id
    messageid = update.callback_query.message.message_id

    # здесь надо обязательно удалить job, удаляющую неактивную игру
    job_removed = remove_job_if_exists(str(id) + "_" + str(rowid), context)

    query.bot.deleteMessage(id, messageid)
    mess = query.bot.send_message(chat_id=id, text="Игра отменена вами!", reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=False, resize_keyboard=True),)
    
def EndOfTheGame(game_data: str):
    ss = game_data.split('_')
    rowid = int(ss[1])
    conn = sqlite3.connect('game.db')
    curs = conn.cursor()
    curs.execute("UPDATE games SET state1 = 5, state2 = 5 WHERE rowid = ?", (rowid,))
    conn.commit()
    curs.execute("SELECT * FROM games WHERE rowid = ?", (rowid,))
    data = curs.fetchall();
    msg1 = data[0][5]
    curs.close()
    conn.close()
    return msg1
    
def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)

def main() -> None:
    """Run the bot."""
    # Create the Updater and pass it your bot's token.
    updater = Updater("")

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher
    main_handler = CommandHandler('start', go_start)

    dispatcher.add_handler(main_handler)

    game = MessageHandler(Filters.regex("Играть!"), run_game)
    dispatcher.add_handler(game)

    callbackQueryRock = CallbackQueryHandler(Rock, pattern='^Rock_')
    dispatcher.add_handler(callbackQueryRock)
    callbackQueryPaper = CallbackQueryHandler(Paper, pattern='^Paper_')
    dispatcher.add_handler(callbackQueryPaper)
    callbackQueryScissors = CallbackQueryHandler(Scissors, pattern='^Scissors_')
    dispatcher.add_handler(callbackQueryScissors)

    callbackQueryCancel = CallbackQueryHandler(Cancel, pattern='^Cancel_')
    dispatcher.add_handler(callbackQueryCancel)
    dispatcher.add_error_handler(error)

    # Start the Bot
    try:
        updater.start_polling()
        print("Bot succesfully started!\nPress Ctrl-C to terminate this")
        logger.info("Bot succesfully started!")
        updater.idle()
    except Exception as ex:
        logger.error("Ошибка запуска бота: %s", ex)

if __name__ == '__main__':
    main()



    
