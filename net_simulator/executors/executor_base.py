import logging
from typing import Dict, List

from a2a.server.agent_execution import AgentExecutor
import httpx
from openai.types.chat import ChatCompletionMessageParam

from net_simulator.utils import get_config


class ExecutorBase(AgentExecutor):
    logger: logging.Logger
    task_messages: Dict[str, List[ChatCompletionMessageParam]]
    agent_id: str

    async def _post_task_start(self):
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"http://localhost:{get_config('system.port')}/task_count/add",
                    json={'agent_id': self.agent_id}
                )
        except Exception:
            pass

    async def _post_task_end(self):
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"http://localhost:{get_config('system.port')}/task_count/delete",
                    json={'agent_id': self.agent_id}
                )
        except Exception:
            pass

    def __init__(self, agent_id: str):
        self.logger = logging.getLogger('uvicorn')
        self.task_messages = {}
        self.agent_id = agent_id
