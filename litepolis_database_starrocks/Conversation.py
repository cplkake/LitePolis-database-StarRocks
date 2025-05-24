from typing import List, Optional, Dict, Any
from uuid import uuid4, UUID
from sqlmodel import Field, Session, SQLModel, select, Relationship, Index
from datetime import datetime, UTC

from .exceptions import ConversationNotFoundError, UnauthorizedConversationUpdateError
from .utils import get_session, is_starrocks_engine

# Define the Conversation model
class Conversation(SQLModel, table=True):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversation_created", "created"),
        Index("ix_conversation_is_archived", "is_archived"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    title: str = Field(nullable=False)
    description: Optional[str] = None
    author_id: UUID = Field(default=None, foreign_key="users.id")
    display_unmoderated: bool = Field(default=False)
    is_archived: bool = Field(default=False)
    created: datetime = Field(default_factory=lambda: datetime.now(UTC))
    modified: datetime = Field(default_factory=lambda: datetime.now(UTC))

    comments: List["Comment"] = Relationship(back_populates="conversation")
    author: Optional["User"] = Relationship(back_populates="conversation",
                                          sa_relationship_kwargs={
                                            "foreign_keys": "Conversation.author_id"})
    pcas: List["UserPca"] = Relationship(back_populates="conversation")
    clusters: List["UserCluster"] = Relationship(back_populates="conversation")


class ConversationManager:
    @staticmethod
    def create_conversation(data: Dict[str, Any]) -> Conversation:
        with get_session() as session:
            conversation_instance = Conversation(**data)
            session.add(conversation_instance)
            session.commit()
            if is_starrocks_engine():
                # StarRocks doesn't support RETURNING, so we fetch the created object
                # based on unique fields. This assumes author_id, title, and description
                # are sufficiently unique for recent inserts.
                return session.exec(
                    select(Conversation).where(
                        Conversation.author_id == data.get("author_id"),
                        Conversation.title == data["title"],
                        Conversation.description == data.get("description")
                    ).order_by(Conversation.created.desc()).limit(1) # Order by created desc to get the most recent match
                ).first()
            session.refresh(conversation_instance)
            return conversation_instance
    
    @staticmethod
    def read_conversation(conversation_id: UUID) -> Optional[Conversation]:
        """Reads a Conversation record by ID.

        Args:
            conversation_id (UUID): The ID of the Conversation to read.

        Returns:
            Optional[Conversation]: The Conversation instance if found, otherwise None.

        Example:
            .. code-block:: python

                from litepolis_database_starrocks import DatabaseActor

                conversation = DatabaseActor.read_conversation(conversation_id=1)
        """
        with get_session as session:
            return session.get(Conversation, conversation_id)

    @staticmethod
    def list_conversations():
        session = get_session()
        conversations = session.exec(select(Conversation)).all()
        session.close()
        return conversations
    
    @staticmethod
    def update_conversation(conversation_id: UUID, current_user_id: UUID, data: Dict[str, Any]) -> Conversation:
        """Updates a Conversation record by ID.

        Args:
            conversation_id (UUID): The ID of the Conversation to update.
            data (Dict[str, Any]): A dictionary containing the data to update.
                                  Allowed keys include 'title', 'description', 'is_archived', and 'author_id'.

        Returns:
            Optional[Conversation]: The updated Conversation instance if found, otherwise None.

        Example:
            .. code-block:: python

                from litepolis_database_starrocks import DatabaseActor

                updated_conversation = DatabaseActor.update_conversation(conversation_id=1, data={"title": "Updated Title"})
        """
        with get_session as session:
            conversation_instance = session.get(Conversation, conversation_id)
            if not conversation_instance:
                raise ConversationNotFoundError(f"Conversation with id {conversation_id} not found.")
            if conversation_instance.author.id != current_user_id:
                raise UnauthorizedConversationUpdateError(f"User is not the author of the conversation.")
            for key, value in data.items():
                setattr(conversation_instance, key, value)
            session.add(conversation_instance)
            session.commit()
            if is_starrocks_engine():
                # StarRocks doesn't support RETURNING, so we fetch the created object
                # based on unique fields.
                return session.exec(
                    select(Conversation)
                    .where(Conversation.id == conversation_id)
                    .order_by(Conversation.created.desc())
                    .limit(1)
                ).first()
            session.refresh(conversation_instance)
            return conversation_instance

    @staticmethod
    def delete_conversation(conversation_id: int):
        session = get_session()
        conversation = session.get(Conversation, conversation_id)
        if not conversation:
            session.close()
            return False

        session.delete(conversation)
        session.commit()
        session.close()
        return True