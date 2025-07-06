import logging
from typing import Dict, List

from a2a.server.agent_execution import AgentExecutor
from openai.types.chat import ChatCompletionMessageParam


class ExecutorBase(AgentExecutor):
    logger: logging.Logger
    task_messages: Dict[str, List[ChatCompletionMessageParam]]

    def __init__(self):
        self.logger = logging.getLogger('uvicorn')
        self.task_messages = {}
