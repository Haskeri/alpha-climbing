"""Подключение к БД средствами SQLAlchemy 2.1 (без расширений Flask)."""
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

# Сессия, привязанная к текущему потоку/запросу; закрывается в teardown_appcontext.
db = scoped_session(sessionmaker(expire_on_commit=False))


def init_db(url):
    engine = create_engine(url, pool_pre_ping=True)
    db.configure(bind=engine)
    return engine


def backend_name():
    return db.get_bind().url.get_backend_name()
