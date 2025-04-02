from litepolis_database_template.Conversations import ConversationManager
import pytest

def test_create_conversation():
    title = "Test Conversation"
    description = "This is a test conversation."
    creator_id = 1
    conversation = ConversationManager.create_conversation(title, description, creator_id)
    assert conversation.title == title
    assert conversation.description == description
    assert conversation.creator_id == creator_id
    conversation_id = conversation.id

    # Clean up
    assert ConversationManager.delete_conversation(conversation_id)


def test_read_conversation():
    # Create a conversation first
    title = "Test Conversation"
    description = "This is a test conversation."
    creator_id = 1
    conversation = ConversationManager.create_conversation(title, description, creator_id)
    conversation_id = conversation.id

    read_conversation = ConversationManager.read_conversation(conversation_id)
    assert read_conversation.title == title
    assert read_conversation.description == description
    assert read_conversation.creator_id == creator_id

    # Clean up
    assert ConversationManager.delete_conversation(conversation_id)


def test_read_conversations():
    # Create some conversations first
    title1 = "Test Conversation 1"
    description1 = "This is a test conversation 1."
    creator_id1 = 1
    ConversationManager.create_conversation(title1, description1, creator_id1)
    title2 = "Test Conversation 2"
    description2 = "This is a test conversation 2."
    creator_id2 = 2
    ConversationManager.create_conversation(title2, description2, creator_id2)

    conversations = ConversationManager.read_conversations()
    assert isinstance(conversations, list)
    assert len(conversations) >= 2  # Assuming there are no other conversations in the database

    # Clean up (very basic, assumes the last two created)
    assert ConversationManager.delete_conversation(conversations[-1].id)
    assert ConversationManager.delete_conversation(conversations[-2].id)


def test_update_conversation():
    # Create a conversation first
    title = "Test Conversation"
    description = "This is a test conversation."
    creator_id = 1
    conversation = ConversationManager.create_conversation(title, description, creator_id)
    conversation_id = conversation.id

    # Update the conversation
    updated_title = "Test Conversation"
    updated_description = "Updated description"
    updated_creator_id = 1
    updated_conversation = ConversationManager.update_conversation(conversation_id, updated_title, updated_description, updated_creator_id)
    assert updated_conversation.description == updated_description

    # Clean up
    assert ConversationManager.delete_conversation(conversation_id)


def test_delete_conversation():
    # Create a conversation first
    title = "Test Conversation"
    description = "This is a test conversation."
    creator_id = 1
    conversation = ConversationManager.create_conversation(title, description, creator_id)
    conversation_id = conversation.id

    # Delete the conversation
    assert ConversationManager.delete_conversation(conversation_id)

    # Try to get the deleted conversation (should return None)
    deleted_conversation = ConversationManager.read_conversation(conversation_id)
    assert deleted_conversation is None
