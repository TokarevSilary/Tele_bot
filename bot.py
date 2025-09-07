import random
from datetime import datetime, timedelta

import psycopg2
import sqlalchemy
import telebot
from sqlalchemy import delete
from sqlalchemy.orm import sessionmaker
from telebot import custom_filters, types
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage

from sql_base import Time, Users, Words, users_time, words_time
from token_keys import admin_name, basa_name, dns, password_admin, token_bot
from translate_func import translate_to_en

state_storage = StateMemoryStorage()
bot = telebot.TeleBot(token_bot,
                      state_storage=state_storage
                      )
engine = sqlalchemy.create_engine(dns)
Session = sessionmaker(bind=engine)
bot.add_custom_filter(custom_filters.StateFilter(bot))
time_for_update = 60

session = Session()


def value_from_base(arg):
    return [x[1] for x in arg[0:4]]


def add_word(user, russian_word, english_word):
    words_from_base = (
        session.query(Words)
        .filter(Words.russian_word == russian_word,
                Words.english_word == english_word)
        .first()
    )
    if not words_from_base:
        new_word = Words(
            russian_word=russian_word,
            english_word=english_word
        )
        session.add(new_word)
        session.commit()
        words_from_base = new_word

    if words_from_base not in user.words:
        user.words.append(words_from_base)
        session.commit()


def get_user_step(uid):
    user = session.query(Users).filter_by(
        telegram_id=uid
    ).first()
    if user:
        return user.user_step
    else:
        new_user = Users(
            telegram_id=uid,
            user_step=0
        )
        session.add(new_user)
        session.commit()

        print("New user detected, added to DB")
        return 0


def cleanup_old_times(session: Session, arg):

    time_threshold = datetime.now() - timedelta(minutes=arg)

    session.execute(
        delete(users_time).where(
            users_time.c.time_id.in_(
                session.query(Time.id).filter(
                    Time.time < time_threshold
                )
            )
        )
    )

    session.execute(
        delete(words_time).where(
            words_time.c.time_id.in_(
                session.query(Time.id).filter(
                    Time.time < time_threshold
                )
            )
        )
    )

    session.query(Time).filter(
        Time.time < time_threshold).delete(
        synchronize_session=False
    )
    session.commit()


class Command:
    ADD_WORD = "Добавить слово ➕"
    DELETE_WORD = "Удалить слово🔙"
    NEXT = "Дальше ⏭"
    START = "/start"


class MyStates(StatesGroup):
    target_word = State()
    translate_word = State()
    another_words = State()
    user_name = State()
    add_word = State()
    manual_add_word = State()


def add_count_time(arg, message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    with bot.retrieve_data(user_id, chat_id) as data:
        target_word = data["target_word"]

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
            print(f"⚠️ Не нашёл запись для "
                  f"{target_word} у юзера {chat_id}")
            session_select.close()
            return
        count = query_date.count
        new_count = count + arg
        print(f"🔄 Обновляю слово {target_word}: "
              f"count {count} → {new_count}")

        query_date.count = new_count
        query_date.time = datetime.now()

        session_select.commit()


def create_cards(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user = session.query(Users).filter_by(
        telegram_id=chat_id).first()

    if not user:
        new_user = Users(
            telegram_id=chat_id,
            user_step=0,
            name=message.from_user.first_name
        )
        session.add(new_user)
        session.commit()

        wordss = session.query(Words).filter_by(
            is_global=True).all()
        for word in wordss:
            if word not in new_user.words:
                new_user.words.append(word)

        session.commit()

    markup = types.ReplyKeyboardMarkup(row_width=2)

    buttons = []
    conn = psycopg2.connect(
        database=basa_name,
        user=admin_name,
        password=password_admin
    )
    with conn.cursor() as cur:
        query = """SELECT russian_word, english_word
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
    pair_our_words = words_from_base[0]
    target_word = pair_our_words[1]
    translate_word = pair_our_words[0]
    shufle_words_from_base = value_from_base(words_from_base)
    option = []
    option.extend(shufle_words_from_base)
    other_word_but = [types.KeyboardButton(word) for word in option]
    buttons.extend(other_word_but)
    random.shuffle(buttons)
    next_btn = types.KeyboardButton(Command.NEXT)
    delete_btn = types.KeyboardButton(Command.DELETE_WORD)
    add_btn = types.KeyboardButton(Command.ADD_WORD)
    buttons.extend([next_btn, delete_btn, add_btn])

    markup.add(*buttons)
    greeting = (f"Выберите перевод слова \n "
                f"{translate_word.upper()}")
    bot.send_message(user_id, greeting, reply_markup=markup)
    bot.set_state(user_id, MyStates.target_word, chat_id)
    with bot.retrieve_data(user_id, chat_id) as data:
        data["target_word"] = target_word
        data["translate_word"] = translate_word
        data["option"] = option
        print(f"Set new card: {data}")


@bot.message_handler(func=lambda message: message.text == Command.DELETE_WORD)
def delete_word(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user = session.query(Users).filter_by(
        telegram_id=chat_id
    ).first()
    with bot.retrieve_data(user_id, chat_id) as data:
        try:
            translate_word = data["translate_word"]
            word = session.query(Words).filter_by(
                russian_word=translate_word
            ).first()
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
    user = session.query(Users).filter(
        Users.telegram_id == chat_id
    ).first()
    english_word = message.text.lower()
    with bot.retrieve_data(user_id, chat_id) as data:
        russian_word = data["russian_word"]
        add_word(user, russian_word, english_word)
        text = (
            f"Добавлена ваша пара слов \n "
            f"{russian_word}--{english_word}\n"
            f"общее количество слов {len(user.words)}"
        )
        bot.send_message(user_id, text)
    bot.delete_state(
        user_id=message.from_user.id,
        chat_id=message.chat.id
    )
    create_cards(message)


@bot.message_handler(state=MyStates.add_word)
def add_word_translate(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    print("я тут")
    user = session.query(Users).filter(
        Users.telegram_id == chat_id
    ).first()
    if message.text == "✅":
        with bot.retrieve_data(user_id, chat_id) as data:
            russian_word = data["russian_word"]
            english_word = data["english_word"]
            add_word(user, russian_word, english_word)
            text = (
                f"<Добавлена пара слов> \n "
                f"{russian_word} -- {english_word}\n"
                f"общее количество слов {len(user.words)}"
            )
            bot.send_message(chat_id, text)
            bot.set_state(user_id, MyStates.target_word, chat_id)
    elif message.text == "❌":
        with bot.retrieve_data(user_id, chat_id) as data:
            russian_word = data["russian_word"]
        text = f"Введите ваш перевод \n {russian_word} "
        bot.send_message(chat_id, text)
        bot.set_state(user_id, MyStates.manual_add_word, chat_id)


@bot.message_handler(
    func=lambda message: message.text
    and not message.text.startswith("/")
    and message.text
    not in [Command.START, Command.NEXT, Command.DELETE_WORD, Command.ADD_WORD]
    and bot.get_state(message.from_user.id, message.chat.id) is None
)
def catch_all(message):
    markup = types.ReplyKeyboardMarkup(row_width=2)
    start_btn = types.KeyboardButton(Command.START)
    markup.add(start_btn)
    bot.send_message(
        message.chat.id,
        f"Привет {message.from_user.first_name}\n"
        f"Нажми кнопку чтобы начать",
        reply_markup=markup,
    )


@bot.message_handler(func=lambda message: message.text == Command.ADD_WORD)
def change_status(message):
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
    buttons_local = []
    accept = "✅"
    refuse = "❌"
    buttons_local.append(accept)
    buttons_local.append(refuse)
    buttons_local.extend(
        [
            types.KeyboardButton(Command.NEXT),
            types.KeyboardButton(Command.DELETE_WORD),
            types.KeyboardButton(Command.ADD_WORD),
        ]
    )
    markup = types.ReplyKeyboardMarkup(
        row_width=2,
        resize_keyboard=True
    )
    markup.add(*buttons_local)
    if translate_to_en(russian_word):
        english_word = translate_to_en(russian_word).strip()
        with bot.retrieve_data(user_id, chat_id) as data:
            data["english_word"] = english_word
            data["russian_word"] = russian_word
        text_accept = f"принять перевод слова {english_word}?"
        bot.send_message(
            chat_id=chat_id,
            text=text_accept,
            reply_markup=markup
        )
        bot.set_state(user_id, MyStates.add_word, chat_id)
    else:
        with bot.retrieve_data(user_id, chat_id) as data:
            data["russian_word"] = russian_word
        text = (f"Перевод не найден \n "
                f"Введите ваш перевод \n "
                f"{russian_word} ")
        bot.send_message(chat_id, text)
        bot.set_state(user_id, MyStates.manual_add_word, chat_id)


session.close()


@bot.message_handler(func=lambda message: message.text == Command.NEXT)
def next_cards(message):
    create_cards(message)


@bot.message_handler(commands=["start", "cards"])
def start(message):
    create_cards(message)


@bot.message_handler(state=MyStates.target_word)
def handle_target_word(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    raw = message.text
    with bot.retrieve_data(user_id, chat_id) as data:
        print(
            f"Checking answer. Data: {data}, "
            f"user_answer: {message.from_user.first_name}"
        )
        target_word = data["target_word"]
        translate_word = data["translate_word"]
        option = data["option"]
        buttons_local = [types.KeyboardButton(w) for w in option]
        buttons_local.extend(
            [
                types.KeyboardButton(Command.NEXT),
                types.KeyboardButton(Command.DELETE_WORD),
                types.KeyboardButton(Command.ADD_WORD),
            ]
        )
        markup = types.ReplyKeyboardMarkup(
            row_width=2,
            resize_keyboard=True)
        markup.add(*buttons_local)

        user_now = session.query(Users).filter_by(
            telegram_id=chat_id
        ).first()
        if not user_now:
            print("User not found in database")
            return
        word_obj = session.query(Words).filter_by(
            english_word=target_word
        ).first()
        if not word_obj:
            print(f"Word '{target_word}' not found in database")
            return

        time_obj = Time(time=datetime.now())
        session.add(time_obj)
        session.commit()

        if user_now and time_obj not in user_now.times:
            user_now.times.append(time_obj)
            session.commit()

        conn = psycopg2.connect(
            database=basa_name,
            user=admin_name,
            password=password_admin
        )
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
        wordss = session.query(Words).filter_by(
            english_word=target_word
        ).first()

        if wordss not in time_obj.words:
            time_obj.words.append(wordss)
            session.commit()
        else:
            rows = session.query(words_time).filter_by(
                word_id=word_obj.id
            ).all()
            for r in rows:
                r.time_id = time_our_id[0]
            session.commit()

        if not target_word or not option:
            create_cards(message)
            return
        elif raw == target_word:
            count = 1
            for btn in buttons_local:
                if btn.text == raw:
                    btn.text = raw + "✅"
                    break
            hint = (f"Молодец ты правильно выбрал \n "
                    f"{translate_word}")
        else:
            count = -1
            for btn in buttons_local:
                if btn.text == raw:
                    btn.text = raw + "❌"
                    break
            hint = (f"Ты неверно выбрал слово \n "
                    f"{translate_word}")
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        markup.add(*buttons_local)
        add_count_time(count, message)
        session.close()

        with Session() as sessions:
            cleanup_old_times(sessions, time_for_update)

        # удаляю все что во времени связано с 0
        time_remove = session.query(Time).filter(
            Time.count == 0
        ).all()
        for time in time_remove:
            time.words.clear()
            time.users.clear()
            session.delete(time)
        session.commit()
        bot.send_message(
            message.chat.id,
            hint,
            reply_markup=markup,
        )


if __name__ == "__main__":
    print("Bot started")
    bot.infinity_polling(skip_pending=True)
