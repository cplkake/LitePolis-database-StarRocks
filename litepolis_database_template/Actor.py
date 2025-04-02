from typing import Dict, Any, List

from .Users import UserManager
from .Conversations import ConversationManager

class DatabaseActor(UserManager, ConversationManager):
    """
    DatabaseActor class for LitePolis.

    This class serves as the central point of interaction between the LitePolis system
    and the database module. It aggregates operations from various manager classes,
    such as UserManager and ConversationManager, providing a unified interface
    for database interactions.

    LitePolis system is designed to interact with a class named "DatabaseActor",
    so ensure this class name is maintained.
    """
    pass