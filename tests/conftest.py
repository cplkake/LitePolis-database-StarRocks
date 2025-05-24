import pytest
from litepolis_database_starrocks import DatabaseActor
from tests.utils import generate_unique_username

@pytest.fixture(scope="function")
def db_session():
    from litepolis_database_starrocks.utils_StarRocks import get_session
    with get_session() as session:
        yield session

@pytest.fixture(scope="function")
def test_user(db_session):
    user_data = {
        "username": generate_unique_username(),
        "hashed_password": "8dd10c7e99d90a2d66b532fb921e40fb"
    }
    user = DatabaseActor.create_user(user_data)
    yield user
    DatabaseActor.delete_user(user.id)