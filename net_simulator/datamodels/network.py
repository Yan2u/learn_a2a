from ast import Tuple
from typing import Any, Dict, List, Literal
from a2a.types import Task
from pydantic import BaseModel

from net_simulator.datamodels.events import StampedTask


class AgentInteraction(BaseModel):
    """
    Represents an interaction between two agents.
    """

    dst_id: str
    message: str


class AgentNetNode(BaseModel):
    """
    Represents a node in the agent network.
    """

    interactions: List[AgentInteraction] = []
    kind: str
    name: str
    category: str
    tasks: Dict[str, StampedTask]


class PublicAgentNode(AgentNetNode):
    """
    Represents a public agent node in the agent network.
    """

    kind: Literal['public'] = 'public'
    task_count: int = 0
    url: str
    lastseen: float
    expose: bool
    visible_to: List[str] | None = None


class UserAgentNode(AgentNetNode):
    """
    Represents a user agent node in the agent network.
    """

    kind: Literal['user'] = 'user'
    conversations: Dict[str, List[Dict[str, Any]]]
    category: str = 'User'
