from sqlmodel import SQLModel, Field, Relationship, select
from typing import Optional, Dict
from uuid import UUID, uuid4

from .utils import get_session, is_starrocks_engine
from .utils_StarRocks import register_table

@register_table(distributed_by="HASH(id)")
class UserPca(SQLModel, table=True):
    __tablename__ = "user_pca"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id")
    conversation_id: UUID = Field(foreign_key="conversations.id")
    x: float
    y: float

    user: Optional["User"] = Relationship(back_populates="user_pcas")
    conversation: Optional["Conversation"] = Relationship(back_populates="pcas")

class UserPcaManager:
    @staticmethod
    def create_userPca(data: Dict[str, any]) -> UserPca:
        with get_session() as session:
            userPca_instance = UserPca(**data)
            session.add(userPca_instance)
            session.commit()
            if is_starrocks_engine():
                # StarRocks doesn't support RETURNING, so we fetch the created object
                # based on unique fields. This assumes text_field, user_id, and
                # conversation_id are sufficiently unique for recent inserts,
                # or that the combination is unique. A better approach might
                # involve a unique constraint or a different ID generation strategy
                # for StarRocks if strict uniqueness is required immediately after insert.
                # For now, this is a pragmatic approach.
                # Note: Including moderation_status in the fetch criteria might be necessary
                # if text_field, user_id, conversation_id are not unique enough.
                # For simplicity, keeping the original fetch logic assuming it's sufficient
                # for the current use case or that ID generation handles uniqueness.
                return session.exec(
                    select(UserPca).where(
                        UserPca.user_id == data.get("user_id"),
                        UserPca.conversation_id == data.get("conversation_id"),
                    ).order_by(UserPca.created.desc()).limit(1) # Order by created desc to get the most recent match
                ).first()
            session.refresh(userPca_instance)
            return userPca_instance
    
    @staticmethod
    def read_userPca_by_user_and_conversation(user_id: UUID, conversation_id: UUID) -> Optional[UserPca]:
        with get_session() as session:
            return session.exec(
                select(UserPca)
                .where(
                    UserPca.converdation_id == conversation_id,
                    UserPca.user_id == user_id,
                )
                .limit(1)
            ).first()