from typing import Optional, List
from net_simulator.msgs.core_msgs import ResponseBase
from pydantic import BaseModel, Field


class AgentInteractionAddRequest(BaseModel):
    """
    Request to add an agent interaction.
    """

    src_id: str
    """
    ID of the source agent.
    """

    dst_id: str
    """
    ID of the destination agent.
    """


class AgentTaskCountAddRequest(BaseModel):
    """
    Request to get the task count for an agent.
    """

    agent_id: str
    """
    ID of the agent.
    """
