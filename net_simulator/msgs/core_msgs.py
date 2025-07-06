from typing import Literal
from pydantic import BaseModel
from typing_extensions import Generic, TypeVar


class ResponseBase(BaseModel):
    """
    Base class for all response models.
    This class can be extended to create specific response models.
    """

    status: Literal['success', 'error'] = 'success'


class ErrorResponse(ResponseBase):
    """
    Represents an error response with a message and an optional error code.
    """

    status: Literal['success', 'error'] = 'error'
    message: str


class TextResponse(ResponseBase):
    content: str


T = TypeVar('T')


class ResponseT(ResponseBase, Generic[T]):
    """
    Generic response model that can hold any type of content.
    This is useful for responses that can vary in structure.
    """

    content: T
