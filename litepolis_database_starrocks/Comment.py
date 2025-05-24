"""
This module defines the database schema for comments, including the `Comment` model
and the `CommentManager` class for managing comment data.

The `Comment` model represents the `comments` table and includes fields for
the comment's content (`text_field`), timestamps (`created`, `modified`),
moderation status (`moderation_status`), and foreign keys linking to the user (`user_id`),
conversation (`conversation_id`), and parent comment (`parent_comment_id`).
It also defines relationships to related `User`, `Conversation`, `Vote`, and other
`Comment` instances (for replies).

The `CommentManager` class provides static methods for common database operations
on comments, such as creating, reading, updating, deleting, listing by various
criteria (conversation, user, date range), searching, and counting.

.. list-table:: Table Schemas
   :header-rows: 1

   * - Table Name
     - Description
   * - users
     - Stores user information (id, username, hashed_password, etc.).
   * - conversations
     - Stores conversation information (id, title, etc.).
   * - comments
     - Stores comment information (id, text_field, user_id, conversation_id, parent_comment_id, created, modified, moderation_status).
   * - votes
     - Stores vote information (id, user_id, comment_id, value).

.. list-table:: Comments Table Details
   :header-rows: 1

   * - Column Name
     - Description
   * - id (UUID)
     - Primary key for the comment.
   * - content (str)
     - The content of the comment.
   * - user_id (UUID, optional)
     - Foreign key referencing the user who created the comment.
   * - conversation_id (UUID, optional)
     - Foreign key referencing the conversation the comment belongs to.
   * - created (datetime)
     - Timestamp of when the comment was created.
   * - modified (datetime)
     - Timestamp of when the comment was last modified.
   * - approved (bool)
     - Status indicating the approved state of the comment.
   * - user (Relationship)
     - Relationship to the User who created the comment.
   * - conversation (Relationship)
     - Relationship to the Conversation the comment belongs to.
   * - votes (Relationship)
     - Relationship to the Votes associated with this comment.

.. list-table:: Classes
   :header-rows: 1

   * - Class Name
     - Description
   * - Comment
     - SQLModel class representing the `comments` table.
   * - CommentManager
     - Provides static methods for managing comments (create, read, update, delete, list, search, count).

To use the methods in this module, import `DatabaseActor` from
`litepolis_database_starrocks`. For example:

.. code-block:: py

    from litepolis_database_starrocks import DatabaseActor

    comment = DatabaseActor.create_comment({
        "text_field": "This is a test comment.",
        "user_id": 0b5078ca-6976-4454-bf0a-b2dd6be2e5f9,
        "conversation_id": d3124f71-4b4a-42e0-b2ef-048da6aef551,
        "approved": True # Include new field if needed, or rely on default
    })
"""

from sqlalchemy import inspect, DDL
from sqlalchemy import ForeignKeyConstraint
from sqlmodel import SQLModel, Field, Relationship, Column, Index, ForeignKey
from sqlmodel import select
from typing import Optional, List, Type, Any, Dict, Generator
from datetime import datetime, UTC
from uuid import uuid4, UUID

from .Actor import DatabaseActor


from .utils import get_session, is_starrocks_engine
from .utils_StarRocks import register_table

@register_table(distributed_by="HASH(id)")
class Comment(SQLModel, table=True):
    __tablename__ = "comments"
    __table_args__ = (
        Index("ix_comment_created", "created"),
        Index("ix_comment_conversation_id", "conversation_id"),
        Index("ix_comment_user_id", "user_id"),
        ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_comment_user_id'),
        ForeignKeyConstraint(['conversation_id'], ['conversations.id'], name='fk_comment_conversation_id')
    )


    id: UUID = Field(primary_key=True, default_factory=uuid4)
    created: datetime = Field(default_factory=lambda: datetime.now(UTC))
    modified: datetime = Field(default_factory=lambda: datetime.now(UTC))
    content: str = Field(nullable=False)
    user_id: Optional[UUID] = Field(default=None, foreign_key="users.id")
    conversation_id: Optional[UUID] = Field(default=None, foreign_key="conversations.id")
    approved: bool = Field(default=False)

    user: Optional["User"] = Relationship(back_populates="comments")
    conversation: Optional["Conversation"] = Relationship(back_populates="comments")
    votes: List["Vote"] = Relationship(back_populates="comment")


class CommentManager:
    @staticmethod
    def create_comment(data: Dict[str, Any]) -> Comment:
        """Creates a new Comment record.

        Args:
            data (Dict[str, Any]): A dictionary containing the data for the new Comment.
                                  Must include 'text_field', 'user_id', 'conversation_id'.
                                  Can optionally include 'parent_comment_id' and 'moderation_status'.

        Returns:
            Comment: The newly created Comment instance.

        Example:
            .. code-block:: py

                from litepolis_database_default import DatabaseActor

                comment = DatabaseActor.create_comment({
                    "text_field": "This is a comment.",
                    "user_id": 1,
                    "conversation_id": 1,
                    "moderation_status": 0
                })
        """
        with get_session() as session:
            comment_instance = Comment(**data)
            session.add(comment_instance)
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
                    select(Comment).where(
                        Comment.user_id == data.get("user_id"),
                        Comment.conversation_id == data.get("conversation_id"),
                        Comment.content == data["content"]
                    ).order_by(Comment.created.desc()).limit(1) # Order by created desc to get the most recent match
                ).first()
            session.refresh(comment_instance)
            return comment_instance

    @staticmethod
    def read_comment(comment_id: UUID) -> Optional[Comment]:
        """Reads a Comment record by ID.

        Args:
            comment_id (UUID): The ID of the Comment to read.

        Returns:
            Optional[Comment]: The Comment instance if found, otherwise None.

        Example:
            .. code-block:: py

                from litepolis_database_default import DatabaseActor

                comment = DatabaseActor.read_comment(comment_id=1)
        """
        with get_session() as session:
            return session.get(Comment, comment_id)
        
    @staticmethod
    def read_next_unvoted_approved_comment(conversation_id: UUID, user_id: UUID, voted_comment_ids: list[UUID]) -> Optional[Comment]:
        with get_session() as session:
            return session.exec(
                select(Comment)
                .where(
                    Comment.conversation_id == conversation_id,
                    Comment.user_id != user_id,
                    Comment.approved,
                    Comment.id.not_in(voted_comment_ids)
                )
                .order_by(Comment.created)
                .limit(1)
            ).first()

    @staticmethod
    def list_comments_by_conversation_id(conversation_id: int, page: int = 1, page_size: int = 10, order_by: str = "created", order_direction: str = "asc") -> List[Comment]:
        """Lists Comment records for a conversation with pagination and sorting.

        Args:
            conversation_id (int): The ID of the conversation to list comments for.
            page (int): The page number to retrieve (default: 1).
            page_size (int): The number of comments per page (default: 10).
            order_by (str): The field to order the comments by (default: "created"). Must be a valid column name of the Comment model.
            order_direction (str): The direction to order the comments in ("asc" or "desc", default: "asc").

        Returns:
            List[Comment]: A list of Comment instances for the given conversation, page, and sorting.

        Example:
            .. code-block:: py

                from litepolis_database_default import DatabaseActor

                comments = DatabaseActor.list_comments_by_conversation_id(conversation_id=1, page=1, page_size=10, order_by="created", order_direction="asc")
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 10
        offset = (page - 1) * page_size
        # Safely get the column for ordering, default to created if invalid
        order_column = getattr(Comment, order_by, Comment.created)
        direction = "asc" if order_direction.lower() == "asc" else "desc"
        sort_order = order_column.asc() if direction == "asc" else order_column.desc()


        with get_session() as session:
            return session.exec(
                select(Comment)
                .where(Comment.conversation_id == conversation_id)
                .order_by(sort_order)
                .offset(offset)
                .limit(page_size)
            ).all()


    @staticmethod
    def update_comment(comment_id: UUID, data: Dict[str, Any]) -> Optional[Comment]:
        """Updates a Comment record by ID.

        Args:
            comment_id (int): The ID of the Comment to update.
            data (Dict[str, Any]): A dictionary containing the data to update.
                                  Keys should match Comment model field names (e.g., 'text_field', 'moderation_status').

        Returns:
            Optional[Comment]: The updated Comment instance if found, otherwise None.

        Example:
            .. code-block:: py

                from litepolis_database_default import DatabaseActor

                updated_comment = DatabaseActor.update_comment(comment_id=1, data={"text_field": "Updated comment text.", "moderation_status": 1})
        """
        with get_session() as session:
            comment_instance = session.get(Comment, comment_id)
            if not comment_instance:
                return None
            for key, value in data.items():
                # Only update if the key is a valid field in the model
                if hasattr(comment_instance, key):
                    setattr(comment_instance, key, value)
            session.add(comment_instance)
            session.commit()
            if is_starrocks_engine():
                # StarRocks doesn't support RETURNING, so we fetch the created object
                # based on unique fields. This assumes text_field, user_id, and
                # conversation_id are sufficiently unique for recent inserts,
                # or that the combination is unique. A better approach might
                # involve a unique constraint or a different ID generation strategy
                # for StarRocks if strict uniqueness is required immediately after insert.
                # For now, this is a pragmatic approach.
                return session.exec(
                    select(Comment).where(
                        Comment.id == comment_id
                    ).order_by(Comment.created.desc()).limit(1) # Order by created desc to get the most recent match
                ).first()
            session.refresh(comment_instance)
            return comment_instance

    @staticmethod
    def delete_comment(comment_id: UUID) -> bool:
        """Deletes a Comment record by ID.

        Args:
            comment_id (UUID): The ID of the Comment to delete.

        Returns:
            bool: True if the Comment was successfully deleted, False otherwise.

        Example:
            .. code-block:: py

                from litepolis_database_default import DatabaseActor

                success = DatabaseActor.delete_comment(comment_id=1)
        """
        with get_session() as session:
            comment_instance = session.get(Comment, comment_id)
            if not comment_instance:
                return False
            session.delete(comment_instance)
            session.commit()
            return True

    @staticmethod
    def search_comments(query: str) -> List[Comment]:
        """Search comments by text content using a LIKE query.

        Args:
            query (str): The search query string. The search will look for
                         comments where the `text_field` contains this string.

        Returns:
            List[Comment]: A list of Comment instances matching the search query.

        Example:
            .. code-block:: py

                from litepolis_database_default import DatabaseActor

                comments = DatabaseActor.search_comments(query="search term")
        """
        search_term = f"%{query}%"
        with get_session() as session:
            return session.exec(
                select(Comment).where(Comment.text_field.like(search_term))
            ).all()

    @staticmethod
    def list_comments_by_user_id(user_id: int, page: int = 1, page_size: int = 10) -> List[Comment]:
        """List comments by user id with pagination.

        Args:
            user_id (int): The ID of the user to list comments for.
            page (int): The page number to retrieve (default: 1).
            page_size (int): The number of comments per page (default: 10).

        Returns:
            List[Comment]: A list of Comment instances for the given user and page.

        Example:
            .. code-block:: py

                from litepolis_database_default import DatabaseActor

                comments = DatabaseActor.list_comments_by_user_id(user_id=1, page=1, page_size=10)
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 10
        offset = (page - 1) * page_size
        with get_session() as session:
            return session.exec(
                select(Comment).where(Comment.user_id == user_id).offset(offset).limit(page_size)
            ).all()

    @staticmethod
    def list_comments_created_in_date_range(start_date: datetime, end_date: datetime) -> List[Comment]:
        """List comments created in a date range.

        Args:
            start_date (datetime): The start date (inclusive) of the range.
            end_date (datetime): The end date (inclusive) of the range.

        Returns:
            List[Comment]: A list of Comment instances created within the given date range.

        Example:
            .. code-block:: py

                from litepolis_database_default import DatabaseActor
                from datetime import datetime, UTC

                start = datetime(2023, 1, 1, tzinfo=UTC)
                end = datetime(2023, 1, 31, tzinfo=UTC)
                comments = DatabaseActor.list_comments_created_in_date_range(start_date=start, end_date=end)
        """
        with get_session() as session:
            return session.exec(
                select(Comment).where(
                    Comment.created >= start_date, Comment.created <= end_date
                )
            ).all()

    @staticmethod
    def count_comments_in_conversation(conversation_id: int) -> int:
        """Counts comments in a conversation.

        Args:
            conversation_id (int): The ID of the conversation to count comments in.

        Returns:
            int: The number of comments in the given conversation. Returns 0 if no comments are found.

        Example:
            .. code-block:: py

                from litepolis_database_default import DatabaseActor

                count = DatabaseActor.count_comments_in_conversation(conversation_id=1)
        """
        with get_session() as session:
            # Use select(func.count()) for potentially better performance on some databases
            # or simply count the results of the select statement.
            # The current scalar(select(...).count()) is also valid SQLModel/SQLAlchemy.
            count = session.scalar(
                select(Comment).where(Comment.conversation_id == conversation_id).count()
            )
            return count if count is not None else 0

    