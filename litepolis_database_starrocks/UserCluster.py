

from sqlmodel import SQLModel, Field, Relationship, select
from sqlalchemy import ForeignKeyConstraint
from uuid import UUID, uuid4
from typing import Optional, Dict

from .utils import get_session, is_starrocks_engine
from .utils_StarRocks import register_table

@register_table(distributed_by="HASH(id)")
class UserCluster(SQLModel, table=True):
    __tablename__ = "user_cluster"
    __table_args__ = (
        ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_comment_user_id'),
        ForeignKeyConstraint(['conversation_id'], ['conversations.id'], name='fk_comment_conversation_id')
    )

    id: UUID = Field(primary_key=True, default_factory=uuid4)
    user_id: UUID = Field(foreign_key="users.id")
    conversation_id: UUID = Field(foreign_key="conversations.id")
    cluster: int

    user: Optional["User"] = Relationship(back_populates="user_cluster")
    conversation: Optional["Conversation"] = Relationship(back_populates="clusters")

class UserClusterManager:
    @staticmethod
    def create_userCluster(data: Dict[str, any]) -> UserCluster:
        with get_session() as session:
            cluster_instance = UserCluster(**data)
            session.add(cluster_instance)
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
                    select(UserCluster).where(
                        UserCluster.user_id == data.get("user_id"),
                        UserCluster.conversation_id == data.get("conversation_id"),
                    ).order_by(UserCluster.created.desc()).limit(1) # Order by created desc to get the most recent match
                ).first()
            session.refresh(cluster_instance)
            return cluster_instance
    
    @staticmethod
    def read_userCluster_by_user_and_conversation(user_id: UUID, conversation_id: UUID) -> Optional[UserPca]:
        with get_session() as session:
            return session.exec(
                select(UserCluster)
                .where(
                    UserCluster.converdation_id == conversation_id,
                    UserCluster.user_id == user_id,
                )
                .limit(1)
            ).first()