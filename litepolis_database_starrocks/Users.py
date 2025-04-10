from typing import Optional

from sqlmodel import Field, Session, SQLModel, select

from .utils import get_session, create_db_and_tables

# Define the SQLModel for users
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str
    password: str
    privilege: str = "user"


class UserManager:
    @staticmethod
    def create_user(email: str, password: str, privilege: str = "user"):
        session = get_session()
        user = User(email=email, password=password, privilege=privilege)
        session.add(user)
        session.commit()
        session.refresh(user)
        session.close()
        return user

    @staticmethod
    def read_user(user_id: int):
        session = with_session()
        user = session.get(User, user_id)
        session.close()
        return user

    @staticmethod
    def read_users():
        session = with_session()
        users = session.exec(select(User)).all()
        session.close()
        return users

    @staticmethod
    def update_user(user_id: int, email: str, password: str, privilege: str):
        session = with_session()
        db_user = session.get(User, user_id)
        if not db_user:
            session.close()
            return None

        db_user.email = email
        db_user.password = password
        db_user.privilege = privilege

        session.add(db_user)
        session.commit()
        session.refresh(db_user)
        session.close()
        return db_user

    @staticmethod
    def delete_user(user_id: int):
        session = with_session()
        user = session.get(User, user_id)
        if not user:
            session.close()
            return False

        session.delete(user)
        session.commit()
        session.close()
        return True

# Run this once to create the database and tables
create_db_and_tables()
