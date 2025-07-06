from pydantic import BaseModel
from net_simulator.msgs.core_msgs import ResponseBase


class AgentKeepAliveRequest(BaseModel):
    agent_id: str


class AgentRegistryInfo(BaseModel):
    """
    Represents the response from an agent registry.
    """
    name: str
    url: str
    agent_id: str


class AgentRegistryRequest(BaseModel):
    """
    A class to represent a registry for agents.
    """

    name: str
    url: str


class AgentRegistryResponse(ResponseBase):
    """
    Represents the response from the agent registry.
    """

    agent_id: str
