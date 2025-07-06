from typing import Optional, List
from net_simulator.msgs.core_msgs import ResponseBase
from pydantic import BaseModel, Field
from a2a.types import TaskState, Message, Artifact, Task


class TaskUpdateRequestBase(BaseModel):
    """
    Base class for task update requests.
    """

    id: str
    """
    Unique identifier for the update event.
    """

    user_id: str
    """
    ID of the related user.
    """


class TaskUpdateRequest(TaskUpdateRequestBase):
    """
    Event of a task update.
    """

    context_id: str
    """
    ID of the context to which the task belongs.
    """

    state: TaskState
    """
    New state of the task.
    """

    messaage: Message | None = None
    """
    Optional message associated with the task update.
    """


class TaskArtifactUpdateRequest(TaskUpdateRequestBase):
    """
    Event of a task status update.
    """

    context_id: str
    """
    ID of the context to which the task belongs.
    """

    artifact: Artifact
    """
    Artifact associated with the task update.
    """


class UserTasksResponse(ResponseBase):
    """
    Response for user tasks requests.
    """

    tasks: List[Task]
    """
    List of task update events for the user.
    """


class UserArtifactsResponse(ResponseBase):
    """
    Response for user artifacts requests.
    """

    artifacts: List[Artifact]
    """
    List of artifacts associated with the user.
    """


class TaskUpdateResponse(ResponseBase):
    """
    Response for task update requests.
    """

    events: List[TaskUpdateRequest | TaskArtifactUpdateRequest]
    """
    List of task update events.
    """
