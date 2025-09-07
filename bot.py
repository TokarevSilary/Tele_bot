import random
from datetime import datetime, timedelta


import psycopg2
import sqlalchemy
from sqlalchemy import delete, update
from sqlalchemy.orm import sessionmaker
import telebot
from telebot import types, custom_filters
from telebot.storage import StateMemoryStorage
from telebot.handler_backends import State, StatesGroup


from sql_base import Users, Words, Time, users_words, users_time, words_time
from token_keys import token_bot, dns, password_admin, basa_name, admin_name
from translate_func import translate_to_en

state_storage = StateMemoryStorage()
bot = telebot.TeleBot(token_bot, state_storage= state_storage )
engine = sqlalchemy.create_engine(dns)
Session = sessionmaker(bind=engine)
bot.add_custom_filter(custom_filters.StateFilter(bot))

session = Session()

known_users = []
userStep = {}

def add_word(user, russian_word, english_word):
    words_from_base = session.query(Words).filter(Words.russian_word == russian_word,
                                                 Words.english_word == english_word).first()
    if not words_from_base:
        new_word = Words(russian_word=russian_word, english_word=english_word)
        session.add(new_word)
        session.commit()
        words_from_base = new_word

    if words_from_base not in user.words:
        user.words.append(words_from_base)
        session.commit()


def get_user_step(uid):
    user = session.query(Users).filter_by(telegram_id=uid).first()
    if user:
        return user.user_step
    else:
        new_user = Users(telegram_id=uid, user_step=0)
        session.add(new_user)
        session.commit()

        print("New user detected, added to DB")
        return 0


def cleanup_old_times(session: Session, arg):
    """Удаляет старые записи времени и связи с ними."""
    time_threshold = datetime.now() - timedelta(minutes = arg)

    # Удаляем связи с users_time
    session.execute(
        delete(users_time).where(users_time.c.time_id.in_(
            session.query(Time.id).filter(Time.time < time_threshold)
        ))
    )

    # Удаляем связи с words_time
    session.execute(
        delete(words_time).where(words_time.c.time_id.in_(
            session.query(Time.id).filter(Time.time < time_threshold)
        ))
    )

    # Удаляем сами записи времени
    session.query(Time).filter(
        Time.time < time_threshold).delete(synchronize_session=False)
    session.commit()



class Command:
    ADD_WORD = 'Добавить слово ➕'
    DELETE_WORD = 'Удалить слово🔙'
    NEXT = 'Дальше ⏭'
    START = '/start'


class MyStates(StatesGroup):
    target_word = State()
    translate_word = State()
    another_words = State()
    user_name = State()
    add_word = State()
    manual_add_word = State()


# def add_count_time(arg, message):
#     user_id = message.from_user.id
#     chat_id = message.chat.id
#
#
#     with bot.retrieve_data(user_id, chat_id) as data:
#         target_word = data['target_word']
#         translate_word = data['translate_word']
#         option = data['option']
#
#         session_select = Session()
#         # subq = session_select.query(users_time).join(user, users_time.user_id == user.c.id).subquery()
#         # times = session_select.query(Time).join(subq, Time.id == subq.c.time_id).all()
#
#         query_date = (
#             session_select.query(Time)
#             .join(users_time, users_time.c.time_id == Time.id)
#             .join(Users, Users.id == users_time.c.user_id)
#             .join(words_time, words_time.c.time_id == Time.id)
#             .join(Words, Words.id == words_time.c.word_id)
#             .filter(Users.telegram_id == chat_id)
#             .filter(Words.english_word == target_word)
#             .first()
#         )
#         last_time = query_date.time
#         count = query_date.count
#
#         hours_passed = (datetime.now() - last_time).total_seconds() / 3600
#
#         if hours_passed > 24 and count > 3:
#             if count > 2:
#                 new_count = count - 2
#             else:
#                 new_count = 0
#
#         else:
#             new_count = count
#             if arg < 0:
#                 new_count = max(0, count + arg)
#             elif arg > 0:
#                 new_count = min(5, count + arg)
#
#         query_date.count = new_count
#         query_date.time = datetime.now()
#         session_select.commit()

def add_count_time(arg, message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    with bot.retrieve_data(user_id, chat_id) as data:
        target_word = data['target_word']

        session_select = Session()

        query_date = (
            session_select.query(Time)
            .join(users_time, users_time.c.time_id == Time.id)
            .join(Users, Users.id == users_time.c.user_id)
            .join(words_time, words_time.c.time_id == Time.id)
            .join(Words, Words.id == words_time.c.word_id)
            .filter(Users.telegram_id == chat_id)
            .filter(Words.english_word == target_word)
            .first()
        )

        if not query_date:
            print(f"⚠️ Не нашёл запись для {target_word} у юзера {chat_id}")
            session_select.close()
            return
        count = query_date.count
        new_count = count + arg
        print(f"🔄 Обновляю слово {target_word}: count {count} → {new_count}")

        query_date.count = new_count
        query_date.time = datetime.now()

        session_select.commit()



def create_cards(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user = session.query(Users).filter_by(telegram_id=chat_id).first()

    if not user:
        new_user = Users(
            telegram_id=chat_id,
            user_step=0,
            name=message.from_user.first_name
        )
        session.add(new_user)
        session.commit()

        wordss = session.query(Words).filter_by(is_global=True).all()
        for word in wordss:
            if word not in new_user.words:
                new_user.words.append(word)

        session.commit()

    markup = types.ReplyKeyboardMarkup(row_width =2)

    buttons = []
    conn = psycopg2.connect(database=basa_name,
                            user=admin_name,
                            password=password_admin)
    with conn.cursor() as cur:
        query = f"""SELECT russian_word, english_word
                FROM public.words w
                Left JOIN public.users_words uw
                ON w.id = uw.word_id
                Left join public.users u
                ON uw.user_id = u.id
                WHERE u.telegram_id = %s
                ORDER BY RANDOM() LIMIT 4;"""
        cur.execute(query, (chat_id,))
        words_from_base = cur.fetchall()
        cur.close()
    conn.close()

    random.shuffle(words_from_base)
    pair_our_words= words_from_base[0]
    target_word = pair_our_words[1]
    translate_word = pair_our_words[0]
    shufle_words_from_base = lambda: [x[1] for x in words_from_base[0:4]]
    option = []
    option.extend(shufle_words_from_base())
    other_word_but = [types.KeyboardButton(word) for word in option]
    buttons.extend(other_word_but)
    random.shuffle(buttons)
    next_btn = types.KeyboardButton(Command.NEXT)
    delete_btn = types.KeyboardButton(Command.DELETE_WORD)
    add_btn = types.KeyboardButton(Command.ADD_WORD)
    buttons.extend([next_btn, delete_btn, add_btn])

    markup.add(*buttons)
    greeting = f"Выберите перевод слова \n {translate_word.upper()}"
    bot.send_message(user_id, greeting, reply_markup=markup)
    bot.set_state(user_id, MyStates.target_word, chat_id)
    with bot.retrieve_data(user_id , chat_id) as data:
        data["target_word"] = target_word
        data["translate_word"] = translate_word
        data["option"] = option
        print(f"Set new card: {data}")

@bot.message_handler(func=lambda message: message.text == Command.DELETE_WORD)
def delete_word(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user = session.query(Users).filter_by(telegram_id=chat_id).first()
    with bot.retrieve_data(user_id, chat_id) as data:
        try:
            translate_word = data["translate_word"]
            word = session.query(Words).filter_by(russian_word = translate_word).first()
            if word and word in user.words:
                user.words.remove(word)
                session.commit()
            text = f"Удалено слово  \n {translate_word}"
        except (KeyError, IndexError):
            return bot.send_message(user_id, "Привет введи слово")
    bot.send_message(user_id, text)
    bot.delete_state(user_id, chat_id)



@bot.message_handler(state=MyStates.manual_add_word)
def manual_add_word(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user = session.query(Users).filter(Users.telegram_id == chat_id).first()
    english_word = message.text.lower()
    with bot.retrieve_data(user_id, chat_id) as data:
        russian_word = data["russian_word"]
        add_word(user, russian_word, english_word)
        text = (f"Добавлена ваша пара слов \n {russian_word}--{english_word}\n"
                f"общее количество слов {len(user.words)}")
        bot.send_message(user_id, text)
    bot.delete_state(user_id=message.from_user.id, chat_id=message.chat.id)
    create_cards(message)



@bot.message_handler(state=MyStates.add_word)
def add_word_translate(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    print("я тут")
    user = session.query(Users).filter(Users.telegram_id == chat_id).first()
    if message.text == "✅":
        with bot.retrieve_data(user_id, chat_id) as data:
            russian_word = data["russian_word"]
            english_word = data["english_word"]
            add_word(user, russian_word, english_word)
            text = (f"<Добавлена пара слов> \n {russian_word} -- {english_word}\n"
                    f"общее количество слов {len(user.words)}")
            bot.send_message(chat_id, text)
            bot.set_state(user_id,MyStates.target_word ,chat_id)
    elif message.text == "❌":
        with bot.retrieve_data(user_id, chat_id) as data:
            russian_word = data["russian_word"]
        text = f"Введите ваш перевод \n {russian_word} "
        bot.send_message(chat_id, text)
        bot.set_state(user_id, MyStates.manual_add_word, chat_id)


@bot.message_handler(
    func=lambda message: message.text and not message.text.startswith("/")
                 and message.text not in [
                     Command.START, Command.NEXT, Command.DELETE_WORD, Command.ADD_WORD
                 ]
                 and bot.get_state(message.from_user.id, message.chat.id) is None
)
def catch_all(message):
    markup = types.ReplyKeyboardMarkup(row_width=2)
    start_btn = types.KeyboardButton(Command.START)
    markup.add(start_btn)
    bot.send_message(
        message.chat.id,
        f"Привет {message.from_user.first_name}\nНажми кнопку чтобы начать",
        reply_markup=markup
    )


@bot.message_handler(func=lambda message: message.text == Command.ADD_WORD)
def change_status (message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    bot.set_state(user_id, MyStates.another_words, chat_id)
    to_user = " Введи слово которое хочешь добавить на русском"
    bot.send_message(chat_id=chat_id, text=to_user)




@bot.message_handler(state=MyStates.another_words)
def another_words(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    russian_word = message.text.lower()
    user = session.query(Users).filter(Users.telegram_id==chat_id).first()
    buttons_local = []
    accept = "✅"
    refuse = "❌"
    buttons_local.append(accept)
    buttons_local.append(refuse)
    buttons_local.extend([
        types.KeyboardButton(Command.NEXT),
        types.KeyboardButton(Command.DELETE_WORD),
        types.KeyboardButton(Command.ADD_WORD)
    ])
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(*buttons_local)
    if translate_to_en(russian_word):
        english_word = translate_to_en(russian_word).strip()
        with bot.retrieve_data(user_id, chat_id) as data:
            data["english_word"] = english_word
            data["russian_word"] = russian_word
        text_accept = f"принять перевод слова {english_word}?"
        bot.send_message(chat_id=chat_id, text=text_accept, reply_markup=markup)
        bot.set_state(user_id, MyStates.add_word, chat_id)
    else:
        with bot.retrieve_data(user_id, chat_id) as data:
            data["russian_word"] = russian_word
        text = (f"Перевод не найден \n "
                f"Введите ваш перевод "
                f"\n {russian_word} ")
        bot.send_message(chat_id, text)
        bot.set_state(user_id, MyStates.manual_add_word, chat_id)
session.close()





@bot.message_handler(func=lambda message: message.text == Command.NEXT)
def next_cards(message):
    create_cards(message)

@bot.message_handler(commands=['start', 'cards'])
def start (message):
    create_cards(message)



@bot.message_handler(state=MyStates.target_word)
def handle_target_word(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    raw = message.text
    with bot.retrieve_data(user_id, chat_id) as data:
        print(f"Checking answer. Data: {data}, "
              f"user_answer: {message.from_user.first_name}")
        target_word = data["target_word"]
        translate_word = data["translate_word"]
        option = data["option"]
        buttons_local = [types.KeyboardButton(w) for w in option]
        buttons_local.extend([
            types.KeyboardButton(Command.NEXT),
            types.KeyboardButton(Command.DELETE_WORD),
            types.KeyboardButton(Command.ADD_WORD)
        ])
        markup = types.ReplyKeyboardMarkup(row_width=2,
                                           resize_keyboard=True)
        markup.add(*buttons_local)
        print(f"Im here 1")

        # count = 0

        time_now = datetime.now()
        user_now = session.query(Users).filter_by(telegram_id=chat_id).first()
        if not user_now:
            print("User not found in database")
            return
        print(f"Im here 2")
        word_obj = session.query(Words).filter_by(english_word=target_word).first()
        if not word_obj:
            print(f"Word '{target_word}' not found in database")
            return
        print(f"Im here 3")
        # time_words = Time(time=datetime.now())
        # session.add(time_words)
        # session.commit()
        time_obj = Time(time=datetime.now())
        session.add(time_obj)
        session.commit()
        # if not time_obj:
        #     # если нет времени, создаём
        #     time_obj = Time(time=time_now)
        #     session.add(time_obj)
        #     session.commit()
        # if not time_obj:
        #     print(f"Word '{target_word}' not found in database")
        #     return
        if user_now and time_obj not in user_now.times:
            user_now.times.append(time_obj)
            session.commit()
        # else:
        #     # psycopg2 обновления
        #     conn = psycopg2.connect(database=basa_name, user="postgres", password=password_admin)
        #     with conn.cursor() as cur:
        #         # обновляем время
        #         cur.execute("""
        #             UPDATE public.time t
        #             SET time = %s
        #             FROM public.users_time ut
        #             JOIN public.words_time wt ON wt.time_id = t.id
        #             WHERE ut.time_id = t.id
        #               AND ut.user_id = %s
        #               AND wt.word_id = %s
        #         """, (time_now, user_now.id, word_obj.id))
        #
        #         # обновляем связь user → time
        #         cur.execute("""
        #             UPDATE public.users_time
        #             SET time_id = %s
        #             WHERE user_id = %s
        #         """, (time_obj.id, user_now.id))
        #
        #     conn.commit()
        #     conn.close()
        print(f"Im here 4")
        conn = psycopg2.connect(database=basa_name,
                                user=admin_name,
                                password=password_admin)
        print(f"Im here 4.5")
        with conn.cursor() as cur:
            query = """SELECT t.id, t.time
                        FROM public.time t
                        JOIN public.users_time ut 
                        ON t.id = ut.time_id
                        WHERE ut.user_id = %s"""

            cur.execute(query, (user_now.id,))
            time_our_id = cur.fetchone()
        conn.close()
        print(f"Im here 4.55 {time_our_id[0]}")
        wordss = session.query(Words).filter_by(english_word=target_word).first()

        # time_words_id = session.query(Time).filter_by(id = time_our_id[0]).first()
        if wordss not in time_obj.words:
            time_obj.words.append(wordss)
            session.commit()
        else:
            # ORM-обновление вместо psycopg2
            rows = session.query(words_time).filter_by(word_id=word_obj.id).all()
            for r in rows:
                r.time_id = time_our_id[0]
            session.commit()

            # conn = psycopg2.connect(database=basa_name, user="postgres", password=password_admin)
            # with conn.cursor() as cur:
            #     query = """UPDATE public.users_time ut
            #                 SET time_id = %s
            #                 FROM public.words_time wt
            #                 WHERE ut.time_id = wt.time_id
            #                 AND ut.user_id = %s
            #                 AND wt.word_id = %s"""
            #     cur.execute(query, (time_words_id, user_now.id, word_obj.id))
            # #     conn.commit()
            # conn.close()
        print(f"Im here 5")
        #
        # wordss = session.query(Words).filter_by(english_word=target_word).first()
        # print(f"Im here 5.5")
        # if wordss not in time_obj.words:
        #     time_obj.words.append(wordss)
        # else:
        #     # >>> Заменено на ORM-обновление
        #     rows = session.query(words_time).filter_by(word_id=word_obj.id).all()
        #     for r in rows:
        #         r.time_id = time_our_id[0]
        #     session.commit()
        print(f"Im here 6")
        #     conn = psycopg2.connect(database=basa_name, user="postgres", password=password_admin)
        #     with conn.cursor() as cur:
        #         cur.execute("SELECT * FROM public.words_time WHERE word_id = %s", (word_obj.id,))
        #         rows = cur.fetchall()
        #         print("Найдено записей:", rows)
        #
        #         print(f"Выполняем UPDATE: user_id={user_now.id}, word_id={word_obj.id}")
        #         query = """
        #             UPDATE public.words_time wt
        #             SET time_id = %s
        #             WHERE word_id = %s
        #             RETURNING wt.word_id, wt.time_id
        #         """
        #         cur.execute(query, (time_our_id[0], word_obj.id))
        #         updated_rows = cur.fetchall()
        #         if updated_rows:
        #             print("Обновлено строк:", updated_rows)
        #         else:
        #             print("Строк для обновления не найдено")
        #     conn.commit()
        #     conn.close()
        # session.commit()

        print(f"Im here 6")
        # count = 0

        if not target_word or not option:
            create_cards(message)
            return
        elif raw == target_word:
            count = 1
            for btn in buttons_local:
                if btn.text == raw:
                    btn.text = raw + '✅'
                    break
            hint = f"Молодец ты правильно выбрал \n {translate_word}"
        else:
            count = -1
            for btn in buttons_local:
                if btn.text == raw:
                    btn.text = raw + '❌'
                    break
            hint = f"Ты неверно выбрал слово \n {translate_word}"
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        markup.add(*buttons_local)
        add_count_time(count, message)
        session.close()

        with Session() as sessions:
            cleanup_old_times(sessions, 60)

        time_remove = session.query(Time).filter(Time.count == 0).all() # удаляю все что во времени связано с 0
        for time in time_remove:
            time.words.clear()
            time.users.clear()
            session.delete(time)
        session.commit()
        bot.send_message(message.chat.id, hint, reply_markup=markup,)
        # bot.delete_state(user_id=message.from_user.id, chat_id=message.chat.id)
        # create_cards(message)




if __name__ == '__main__':
    print('Bot started')
    bot.polling(none_stop=True)
    # bot.infinity_polling(skip_pending=True)
