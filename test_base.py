from sqlalchemy.orm import sessionmaker
from sql_base import Users, Words, users_words, engine

Session = sessionmaker(bind=engine)
session = Session()

def test_add():
    user = session.query(Users).first()

    words = session.query(Words).filter_by(is_global=True).all()
    for word in words:
        print(f"Пробуем связать: {user.telegram_id} ↔ {word.russian_word}")

        # Добавляем связь, если её нет
        if word not in user.words:
            user.words.append(word)


if __name__ == "__main__":
    test_add()