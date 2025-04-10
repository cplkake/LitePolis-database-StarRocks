import os
from sqlmodel import Session, SQLModel, create_engine

from litepolis import get_config

DEFAULT_CONFIG = {
    "starrocks_url": "mysql+pymysql://root:@127.0.0.1:9030/litepolis"
}

if ("PYTEST_CURRENT_TEST" not in os.environ and
    "PYTEST_VERSION" not in os.environ):
    database_url = get_config("litepolis_database_starrocks", "starrocks_url")
else:
    database_url = DEFAULT_CONFIG.get("starrocks_url")
engine = create_engine(database_url)

def connect_db():
    engine = create_engine(database_url)

def create_db_and_tables():
    # SQLModel.metadata.create_all() has checkfirst=True by default
    # so tables will only be created if they don't exist
    SQLModel.metadata.create_all(engine)

def get_session():
    return Session(engine)