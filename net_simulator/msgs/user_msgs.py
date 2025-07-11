from typing import List
from pydantic import BaseModel
from net_simulator.msgs.core_msgs import ResponseBase


class UserRegisterRequest(BaseModel):
    """
    Represents a request to register a user.
    This class can be extended to include additional fields as needed.
    """
    user_id: str
    user_name: str


class UserChatRequest(BaseModel):
    """
    Represents a request to send a chat message from a user.
    """

    user_id: str
    """
    ID of the user sending the chat message.
    """

    conversation_id: str
    """
    ID of the conversation to which the message belongs.
    """

    message: str
    """
    The chat message content sent by the user.
    """


class UserMessageResponse(ResponseBase):
    """
    Represents a response to a user message.
    This class can be extended to include additional fields as needed.
    """

    user_id: str
    """
    ID of the user who sent the message.
    """

    messages: List[dict]
    """
    List of messages associated with the user.
    """


class UserConversationsResponse(ResponseBase):
    """
    Represents a response containing all conversations for a user.
    This class can be extended to include additional fields as needed.
    """

    user_id: str
    """
    ID of the user whose conversations are being returned.
    """

    conversations: List[str]
    """
    List of conversation IDs associated with the user.
    """
