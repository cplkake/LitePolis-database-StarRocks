class ConversationNotFoundError(Exception):
    """Raised when a conversation with the given ID does not exist."""
    pass

class UnauthorizedConversationUpdateError(Exception):
    """Raised when a user tries to update a conversation they do not own."""
    pass
