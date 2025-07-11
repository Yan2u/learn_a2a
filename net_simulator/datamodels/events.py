from typing import List
from a2a.types import Task, Artifact


class StampedTask(Task):
    """
    Represents a task with a timestamp.
    """

    timestamp: str
