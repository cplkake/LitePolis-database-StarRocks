from typing import List, Optional

from sqlmodel import Field, Session, SQLModel, select

from .utils import get_session, create_db_and_tables

# Define the Conversation model
class Conversation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: str
    creator_id: int
    # moderation: bool = False # Add moderation if needed


class ConversationManager:
    @staticmethod
    def create_conversation(title: str, description: str, creator_id: int):
        session = get_session()
        conversation = Conversation(title=title,
                                    description=description,
                                    creator_id=creator_id)
        session.add(conversation)
        session.commit()
        session.refresh(conversation)
        session.close()
        return conversation

    @staticmethod
    def read_conversations():
        session = get_session()
        conversations = session.exec(select(Conversation)).all()
        session.close()
        return conversations

    @staticmethod
    def read_conversation(conversation_id: int):
        session = get_session()
        conversation = session.get(Conversation, conversation_id)
        session.close()
        return conversation

    @staticmethod
    def update_conversation(conversation_id: int, title: str,
                            description: str, creator_id: int):
        session = get_session()
        db_conversation = session.get(Conversation, conversation_id)
        if not db_conversation:
            session.close()
            return None

        db_conversation.title = title
        db_conversation.description = description
        db_conversation.creator_id = creator_id

        session.add(db_conversation)
        session.commit()
        session.refresh(db_conversation)
        session.close()
        return db_conversation

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

# Run this once to create the database and tables
create_db_and_tables()
