import pytest
from litepolis_database_starrocks import DatabaseActor
from tests.utils import generate_unique_username



def test_create_conversation(db_session, test_user): 
    # Create conversation
    conversation_data = {
        "title": "Test Conversation",
        "description": "This is a test conversation",
        "author_id": test_user.id
    }
    conversation = DatabaseActor.create_conversation(conversation_data)
    
    assert conversation.id is not None
    assert conversation.title == conversation_data["title"]
    assert conversation.description == conversation_data["description"]
    assert conversation.author_id == conversation_data["author_id"]

    # Clean up
    assert DatabaseActor.delete_conversation(conversation.id)


def test_delete_conversation(db_session, test_user):
    # Create a conversation first
    conversation_data = {
        "title": "Test Conversation",
        "description": "This is a test conversation.",
        "author_id": test_user.id
    }
    conversation = DatabaseActor.create_conversation(conversation_data)
    conversation_id = conversation.id

    # Delete the conversation
    assert DatabaseActor.delete_conversation(conversation_id)

    # Try to get the deleted conversation (should return None)
    deleted_conversation = DatabaseActor.read_conversation(conversation_id)
    assert deleted_conversation is None


def test_read_conversation(db_session, test_user):
    # Create conversation
    conversation_data = {
        "title": "Get Test Conversation",
        "description": "Getting this one",
        "author_id": test_user.id
    }
    conversation = DatabaseActor.create_conversation(conversation_data)
    
    # Retrieve conversation
    retrieved_conversation = DatabaseActor.read_conversation(conversation.id)
    
    assert retrieved_conversation.id == conversation.id
    assert retrieved_conversation.title == conversation_data["title"]
    assert retrieved_conversation.description == conversation_data["description"]
    assert retrieved_conversation.author_id == conversation_data["author_id"]

    # Clean up
    assert DatabaseActor.delete_conversation(conversation.id)


def test_list_conversations(db_session, test_user):
    # Create conversations
    conversation1_data = {
        "title": "Test Conversation 1",
        "description": "Test description for conversation 1",
        "author_id": test_user.id
    }
    conversation1 = DatabaseActor.create_conversation(conversation1_data)
    conversation2_data = {
        "title": "Test Conversation 2",
        "description": "Test description for conversation 2",
        "author_id": test_user.id
    }
    conversation2 = DatabaseActor.create_conversation(conversation2_data)
    
    conversations = DatabaseActor.list_conversations()
    titles = [conv.title for conv in conversations]
    
    assert isinstance(conversations, list), "Expected a list of conversations"
    assert conversation1.title in titles
    assert conversation2.title in titles

    # Clean up 
    assert DatabaseActor.delete_conversation(conversation1.id)
    assert DatabaseActor.delete_conversation(conversation2.id)


def test_list_conversations_pagination(db_session, test_user):
    # Create 15 conversations
    conversations = []
    for i in range(15):
        conv = DatabaseActor.create_conversation({
            "title": f"Test Pagination {i}",
            "description": "Paginated",
            "author_id": test_user.id
        })
        conversations.append(conv)

    # Page 1 with page_size=10
    page1 = DatabaseActor.list_conversations(page=1, page_size=10)
    assert len(page1) == 10

    # Page 2 should have 5
    page2 = DatabaseActor.list_conversations(page=2, page_size=10)
    assert len(page2) == 5

    # Clean up
    for conv in conversations:
        DatabaseActor.delete_conversation(conv.id)


def test_list_conversations_ordering(db_session, test_user):
    # Create conversations with different titles
    conv1 = DatabaseActor.create_conversation({
        "title": "Alpha",
        "description": "Sorting test",
        "author_id": test_user.id
    })
    conv2 = DatabaseActor.create_conversation({
        "title": "Beta",
        "description": "Sorting test",
        "author_id": test_user.id
    })

    results = DatabaseActor.list_conversations(order_by="title", order_direction="asc")
    titles = [c.title for c in results]

    # Ensure Alpha comes before Beta
    alpha_index = titles.index("Alpha") if "Alpha" in titles else -1
    beta_index = titles.index("Beta") if "Beta" in titles else -1
    assert alpha_index != -1 and beta_index != -1
    assert alpha_index < beta_index

    # Clean up
    DatabaseActor.delete_conversation(conv1.id)
    DatabaseActor.delete_conversation(conv2.id)


def test_update_conversation(db_session, test_user):
    # Create a conversation first
    data = {
        "title": "Test Conversation",
        "description": "This is a test conversation.",
        "author_id": test_user.id
    }
    conversation = DatabaseActor.create_conversation(data)
    conversation_id = conversation.id

    # Update the conversation
    updated_data = {
        "title": "Updated Title",
        "description": "Updated description",
        "is_archived": True,
    }
    updated_conversation = DatabaseActor.update_conversation(conversation_id, updated_data)
    assert updated_conversation.title == updated_data["title"]
    assert updated_conversation.description == updated_data["description"]
    assert updated_conversation.is_archived == updated_data["is_archived"]

    # Clean up
    assert DatabaseActor.delete_conversation(conversation_id)