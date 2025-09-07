
from token_keys import token_bot

from telebot import TeleBot
from telebot.storage import StateMemoryStorage
from telebot.handler_backends import State, StatesGroup



from telebot import TeleBot, types, custom_filters
from telebot.storage import StateMemoryStorage
from telebot.handler_backends import State, StatesGroup

token = token_bot
state_storage = StateMemoryStorage()
bot = TeleBot(token, state_storage=state_storage)

# Подключаем фильтры состояний
bot.add_custom_filter(custom_filters.StateFilter(bot))

class MyStates(StatesGroup):
    target_word = State()

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Введите слово:")
    bot.set_state(message.from_user.id, MyStates.target_word, message.chat.id)

@bot.message_handler(state=MyStates.target_word)
def debug_target_state(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    with bot.retrieve_data(user_id, chat_id) as data:
        bot.send_message(chat_id,
                         f"FSM видит target_word!\nТекст: {message.text}\nДанные: {data}")

bot.infinity_polling()