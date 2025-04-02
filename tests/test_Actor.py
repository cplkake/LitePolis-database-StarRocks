from litepolis_database_template import DatabaseActor


def test_actor_create_user_and_conversation():
    user = DatabaseActor.create_user("actor_test@example.com", "password", "user")
    creator_id = user.id
    
    conversation =  DatabaseActor.create_conversation("Actor Test Title", "Actor Test Description", creator_id)
    assert conversation.title == "Actor Test Title"
    
    # Cleanup
    DatabaseActor.delete_conversation(conversation.id)
    DatabaseActor.delete_user(creator_id)
