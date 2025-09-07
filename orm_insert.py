import psycopg2
import sqlalchemy
from sqlalchemy.orm import sessionmaker
from token_keys import dns
from sql_base import create_tabele, delete_tabele
from sql_base import Words
engine = sqlalchemy.create_engine(dns)
Session = sessionmaker(bind=engine)

engine = sqlalchemy.create_engine(dns)
delete_tabele(engine)
create_tabele(engine)


session = Session()

words = [
    {"russian_word" : 'машина', "english_word" : 'car', "is_global" : True},
    {"russian_word" : 'полный', "english_word" : 'full', "is_global" : True},
    {"russian_word" : 'солнце', "english_word" : 'Sun', "is_global" : True},
    {"russian_word" : 'заяц', "english_word" : 'rabbit', "is_global" : True},
    {"russian_word" : 'школа', "english_word" : 'school', "is_global" : True},
    {"russian_word" : 'карусель', "english_word" : 'roundabout', "is_global" : True},
    {"russian_word" : 'муха', "english_word" : 'fly', "is_global" : True},
    {"russian_word" : 'космос', "english_word" : 'space', "is_global" : True},
    {"russian_word" : 'яма', "english_word" : 'pit', "is_global" : True},
    {"russian_word" : 'прекрасный', "english_word" : 'beautiful', "is_global" : True},
]

for w in words:
    word_obj = Words(**w)
    session.add(word_obj)
session.commit()
session.close()

# def test_add():
#     user = session.query(Users).first()
#
#     wordss = session.query(Words).filter_by(is_global=True).all()
#     for word in wordss:
#         print(f"Пробуем связать: {user.telegram_id} ↔ {word.russian_word}")
#
#         # Добавляем связь, если её нет
#         if word not in user.words:
#             user.words.append(word)
#
#
# if __name__ == "__main__":
#     test_add()

# new_words = Words(russian_word='машина', english_word='<UNK>', is_global=True)