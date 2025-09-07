import psycopg2
import sqlalchemy
import sqlalchemy as sq
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from token_keys import dns

Base = declarative_base()
engine = sqlalchemy.create_engine(dns)
Session = sessionmaker(bind=engine)


users_words = sq.Table(
    "users_words",
    Base.metadata,
    sq.Column(
        "user_id",
        sq.Integer,
        sq.ForeignKey("users.id"),
        primary_key=True,
        nullable=False,
    ),
    sq.Column(
        "word_id",
        sq.Integer,
        sq.ForeignKey("words.id"),
        primary_key=True,
        nullable=False,
    ),
)


users_time = sq.Table(
    "users_time",
    Base.metadata,
    sq.Column(
        "user_id",
        sq.Integer,
        sq.ForeignKey("users.id"),
        primary_key=True,
        nullable=True,
    ),
    sq.Column(
        "time_id",
        sq.Integer,
        sq.ForeignKey("time.id"),
        primary_key=True,
        nullable=True
    ),
)


words_time = sq.Table(
    "words_time",
    Base.metadata,
    sq.Column(
        "word_id",
        sq.Integer,
        sq.ForeignKey("words.id"),
        primary_key=True,
        nullable=True,
    ),
    sq.Column(
        "time_id",
        sq.Integer,
        sq.ForeignKey("time.id"),
        primary_key=True,
        nullable=True
    ),
)


class Users(Base):
    __tablename__ = "users"
    id = sq.Column(sq.Integer, primary_key=True)
    telegram_id = sq.Column(sq.BigInteger, nullable=False, unique=True)
    name = sq.Column(sq.String(50), nullable=True)
    user_step = sq.Column(sq.Integer, nullable=True)
    words = relationship("Words",
                         secondary=users_words,
                         backref="users")
    times = relationship("Time",
                         secondary=users_time,
                         backref="users")


class Words(Base):
    __tablename__ = "words"
    id = sq.Column(sq.Integer, primary_key=True)
    russian_word = sq.Column(sq.String(100),
                             nullable=False,
                             index=True
                             )
    english_word = sq.Column(sq.String(100),
                             nullable=False,
                             index=True
                             )
    is_global = sq.Column(sq.Boolean,
                          nullable=False,
                          default=False
                          )
    __table_args__ = (
        sq.UniqueConstraint(
            "russian_word",
            "english_word",
            name="unique_word_pair"
        ),
    )
    times = relationship(
        "Time",
        secondary=words_time,
        backref="words"
    )


class Time(Base):
    __tablename__ = "time"
    id = sq.Column(sq.Integer, primary_key=True)
    time = sq.Column(sq.DateTime, nullable=False)
    count = sq.Column(sq.Integer, nullable=False, default=0)


def create_tabele(engine):
    Base.metadata.create_all(engine)


def delete_tabele(engine):
    Base.metadata.drop_all(engine)
