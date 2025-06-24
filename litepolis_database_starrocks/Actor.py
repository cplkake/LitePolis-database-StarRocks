from typing import Dict, Any, List

from .Comment import Comment, CommentManager
from .Conversation import Conversation, ConversationManager
from .UserCluster import UserCluster, UserClusterManager
from .UserPca import UserPca, UserPcaManager
from .User import UserManager, UserManager
from .Vote import Vote, VoteManager

from .utils_StarRocks import create_db_and_tables
print("Calling create_db_and_tables()")
create_db_and_tables()

class DatabaseActor(
    CommentManager,
    ConversationManager,
    UserClusterManager,
    UserPcaManager,
    UserManager,
    VoteManager,
):
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