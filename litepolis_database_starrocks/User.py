from typing import Optional, Dict, Any, List
from sqlmodel import Field, Session, SQLModel, select, UniqueConstraint, Index, String, Relationship
from uuid import uuid4, UUID
from datetime import datetime, UTC

from .utils import get_session, is_starrocks_engine
from .utils_StarRocks import register_table

@register_table(distributed_by="HASH(id)")
class User(SQLModel, table=True):
    __tablename__ = "users"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    username: str = Field(String(50), nullable=False, unique=not is_starrocks_engine())
    hashed_password: str = Field(nullable=False)
    created: datetime = Field(default_factory=lambda: datetime.now(UTC))

    conversations: List["Conversation"] = Relationship(back_populates="author")
    comments: List["Comment"] = Relationship(back_populates="user")
    votes: List["Vote"] = Relationship(back_populates="user")
    user_clusters: List["UserCluster"] = Relationship(back_populates="user")
    user_pcas: List["UserPca"] = Relationship(back_populates="user")



class UserManager:
    @staticmethod
    def create_user(data: Dict[str, Any]) -> Optional[User]:
        """Creates a new User record.

        Handles checking for existing username before creation, especially for StarRocks.

        Args:
            data: A dictionary containing user data (e.g., "username", "auth_token").

        Returns:
            The created User object, or None if a user with the same username already exists.

        To use this method, import DatabaseActor.  For example::

            from litepolis_database_starrocks import DatabaseActor

            user = DatabaseActor.create_user({
                "username": "testUser",
                "hashed_password": "qwertyuiop",
            })
        """
        if is_starrocks_engine():
            with get_session() as session:
                existing_username = session.exec(
                    select(User.username).where(User.username == data["username"])
                ).first()
            
            if existing_username is not None:
                print(f"User {data['username']} already exists")
                return None
                
        user = User(**data)
        with get_session() as session:
            session.add(user)
            session.commit()
            # StarRocks might not return the ID immediately on commit,
            # so we fetch the created user explicitly.
            if is_starrocks_engine():
                return session.exec(
                    select(User).where(User.username == data["username"])
                ).first()
            session.refresh(user)
            return user
    
    @staticmethod
    def read_user(user_id: UUID) -> Optional[User]:
        """Reads a User record by ID.

        Args:
            user_id: The unique identifier of the user.

        Returns:
            The User object if found, otherwise None.

        To use this method, import DatabaseActor.  For example::

            from litepolis_database_starrocks import DatabaseActor

            user = DatabaseActor.read_user(user_id=9f4325a4-b840-4e30-8338-e5caea622797)
        """
        with get_session() as session:
            return session.get(User, user_id)

    @staticmethod
    def read_user_by_username(username: str) -> Optional[User]:
        """Reads a User record by username.

        Args:
            username: The unique string identifier of the user.

        Returns:
            The User object if found, otherwise None.

        To use this method, import DatabaseActor.  For example::

            from litepolis_database_starrocks import DatabaseActor

            user = DatabaseActor.read_user_by_username(username=testUser)
        """
        with get_session() as session:
            return session.exec(select(User).where(User.username == username)).first()
        
    @staticmethod
    def list_users(page: int = 1, page_size: int = 10) -> List[User]:
        """Lists User records with pagination.

        Args:
            page: The page number (1-based). Defaults to 1.
            page_size: The number of records per page. Defaults to 10.

        Returns:
            A list of User objects for the specified page.

        To use this method, import DatabaseActor.  For example::

            from litepolis_database_default import DatabaseActor

            users = DatabaseActor.list_users(page=1, page_size=10)
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 10
        offset = (page - 1) * page_size
        with get_session() as session:
            return session.exec(select(User).offset(offset).limit(page_size)).all()

    @staticmethod
    def update_user(user_id: UUID, data: Dict[str, Any]) -> Optional[User]:
        """Updates a User record by ID with the provided data.

        Args:
            user_id: The unique identifier of the user to update.
            data: A dictionary containing the fields and new values to update.

        Returns:
            The updated User object if found and updated, otherwise None.

        To use this method, import DatabaseActor.  For example::

            from litepolis_database_starrocks import DatabaseActor

            user = DatabaseActor.update_user(user_id=9f4325a4-b840-4e30-8338-e5caea622797, data={"username": "realUser"})
        """
        with get_session() as session:
            user_instance = session.get(User, user_id)
            if not user_instance:
                return None
            # Optional StarRocks-only uniqueness check for username
            if is_starrocks_engine() and "username" in data:
                existing_username = session.exec(
                    select(User.username).where(User.username == data["username"])
                ).first()
                if existing_username is not None:
                    print(f"User {data['username']} already exists")
                    return None
            # Only allow updating fields that exist in the user model
            valid_fields = User.model_fields.keys()
            filtered_data = {
                key: value
                for key, value in data.items()
                if key in valid_fields
            }
            for key, value in filtered_data.items():
                setattr(user_instance, key, value)
            session.add(user_instance)
            session.commit()
            if is_starrocks_engine():
                # StarRocks might not reflect updates immediately in the same session,
                # so do a full query to ensure data is loaded correctly.
                return session.exec(
                    select(User).where(User.id == user_id)
                ).first()
            session.refresh(user_instance)
            return user_instance
    
    @staticmethod
    def delete_user(user_id: UUID) -> bool:
        """Deletes a User record by ID.

        Args:
            user_id: The unique identifier of the user to delete.

        Returns:
            True if the user was found and deleted, False otherwise.

        To use this method, import DatabaseActor.  For example::

            from litepolis_database_starrocks import DatabaseActor

            success = DatabaseActor.delete_user(user_id=9f4325a4-b840-4e30-8338-e5caea622797)
        """
        with get_session() as session:
            user_instance = session.get(User, user_id)
            if not user_instance:
                return False
            session.delete(user_instance)
            session.commit()
            return True
    
    @staticmethod
    def list_users_created_in_date_range(start_date: datetime, end_date: datetime) -> List[User]:
        """Lists users created within a specified date range (inclusive).

        Args:
            start_date: The start of the date range.
            end_date: The end of the date range.

        Returns:
            A list of User objects created within the specified range.

        To use this method, import DatabaseActor.  For example::

            from litepolis_database_starrocks import DatabaseActor

            users = DatabaseActor.list_users_created_in_date_range(start_date=datetime(2023, 1, 1), end_date=datetime(2023, 12, 31))
        """
        with get_session() as session:
            return session.exec(
                select(User).where(User.created >= start_date, User.created <= end_date)
            ).all()

    @staticmethod
    def count_users() -> int:
        """Counts the total number of User records in the database.

        Returns:
            The total count of users.

        To use this method, import DatabaseActor.  For example:

            from litepolis_database_starrocks import DatabaseActor

            count = DatabaseActor.count_users()
        """
        with get_session() as session:
            return session.scalar(select(User).count()) or 0