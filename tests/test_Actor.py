from litepolis_database_starrocks import DatabaseActor
from tests.utils import generate_unique_username


def test_actor_create_user_and_conversation():
    user_data = {
        "username": generate_unique_username(),
        "hashed_password": "password"
    }
    user = DatabaseActor.create_user(user_data)
    author_id = user.id
    
    conversation_data = {
        "title": "Actor Test Title",
        "description": "Actor Test Description",
        "author_id": author_id
    }
    conversation = DatabaseActor.create_conversation(conversation_data)
    assert conversation.title == conversation_data["title"]
    
    # Cleanup
    DatabaseActor.delete_conversation(conversation.id)
    DatabaseActor.delete_user(author_id)