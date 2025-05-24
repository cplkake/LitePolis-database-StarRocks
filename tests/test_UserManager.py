import pytest
from litepolis_database_starrocks import DatabaseActor
from tests.utils import generate_unique_username


def test_create_user(db_session):
    user_data = {
        "username": generate_unique_username(),
        "hashed_password": "8dd10c7e99d90a2d66b532fb921e40fb",
    }
    user = DatabaseActor.create_user(user_data)

    assert user.id is not None
    assert user.email == user_data["username"]
    assert user.hashed_password == user_data["hashed_password"]

    # Clean up
    assert DatabaseActor.delete_user(user.id)


def test_read_user(db_session):
    # Create a user first
    user_data = {
        "username": generate_unique_username(),
        "hashed_password": "8dd10c7e99d90a2d66b532fb921e40fb",
    }

    user = DatabaseActor.create_user(user_data)
    user_id = user.id

    read_user = DatabaseActor.read_user(user_id)
    assert read_user is not None
    assert read_user.email == user_data["username"]

    # Clean up
    assert DatabaseActor.delete_user(user_id)

def test_read_user_by_username(db_session):
    # Create a user first
    user_data = {
        "username": generate_unique_username(),
        "hashed_password": "8dd10c7e99d90a2d66b532fb921e40fb",
    }

    user = DatabaseActor.create_user(user_data)
    user_id = user.id

    read_user = DatabaseActor.read_user_by_username(user_data["username"])
    assert read_user is not None
    assert read_user.email == user_data["username"]

    # Clean up
    assert DatabaseActor.delete_user(user_id)


def test_list_users(db_session):
    # Create some users first
    user1_data = {
        "username": generate_unique_username(),
        "hashed_password": "8dd10c7e99d90a2d66b532fb921e40fb",
    }
    user2_data = {
        "username": generate_unique_username(),
        "hashed_password": "bda53c18bdbf90dc4221f8209fcb3bda",
    }
    user1 = DatabaseActor.create_user(user1_data)
    user2 = DatabaseActor.create_user(user2_data)

    users = DatabaseActor.list_users()
    assert isinstance(users, list)
    assert len(users) >= 2

    # Clean up (very basic, assumes the last two created)
    assert DatabaseActor.delete_user(user1.id)
    assert DatabaseActor.delete_user(user2.id)


def test_update_user(db_session):
    # Create a user first
    user_data = {
        "username": generate_unique_username(),
        "hashed_password": "8dd10c7e99d90a2d66b532fb921e40fb"
    }
    user = DatabaseActor.create_user(user_data)
    user_id = user.id

    # Update the user
    updated_user_data = {
        "username": generate_unique_username(),
        "hashed_password": "bda53c18bdbf90dc4221f8209fcb3bda"
    }
    updated_user = DatabaseActor.update_user(
        user_id,
        updated_user_data
    )
    assert updated_user.username == updated_user_data["username"]
    assert updated_user.hashed_password == "bda53c18bdbf90dc4221f8209fcb3bda"

    # Clean up
    assert DatabaseActor.delete_user(user_id)


def test_delete_user(db_session):
    # Create a user first
    user_data = {
        "username": generate_unique_username(),
        "hashed_password": "8dd10c7e99d90a2d66b532fb921e40fb"
    }
    user = DatabaseActor.create_user(user_data)
    user_id = user.id

    assert DatabaseActor.delete_user(user_id)

    # Try to get the deleted user (should return None)
    deleted_user = DatabaseActor.read_user(user_id)
    assert deleted_user is None
