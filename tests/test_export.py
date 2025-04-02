import pytest
from litepolis_database_template import Actor, DEFAULT_CONFIG

def test_actor_name():
    """Verify the DatabaseActor class name."""
    assert Actor.DatabaseActor.__name__ == "DatabaseActor"

def test_actor_exposure():
    """Check if DatabaseActor and DEFAULT_CONFIG are exposed."""
    assert hasattr(Actor, "DatabaseActor")
    assert DEFAULT_CONFIG is not None  # Or a more specific check
