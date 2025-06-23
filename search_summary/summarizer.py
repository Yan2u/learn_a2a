import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    InternalError
)
from a2a.utils.errors import ServerError

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import TaskState, TextPart, Message
import json

from a2a.client import A2ACardResolver, A2AClient

from a2a.utils import new_agent_text_message

import os
from dotenv import load_dotenv
import llm_chat

SYSTEM_PROMPT = """
You are a helpful assistant that summarizes search engine results. You will be given a list of search results in JSON format.
Your task is to generate a Markdown report. The report must contain exactly two sections:
1. An H3 heading '### 一、Brief' followed by a concise summary of the findings based on all the provided search results.
2. An H3 heading '### 二、Table' followed by a Markdown table of all the provided results. The table should have columns for 'Title', 'Description', and 'URL'. The URL should be a clickable link.

Do not add any other text, introductions, or conclusions. The entire output must be a single Markdown block.
"""


class SummarizerExecutor(AgentExecutor):

    def __init__(self):
        pass

    async def execute(self, context: RequestContext, event_queue: EventQueue):
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        if not context.current_task:
            await updater.update_status(TaskState.submitted)

        query = context.get_user_input()
        try:
            async for chunk in llm_chat.get_llm_response_stream(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=query
            ):
                if chunk:
                    await updater.update_status(
                        TaskState.working,
                        new_agent_text_message(
                            text=chunk,
                            context_id=context.context_id,
                            task_id=context.task_id,
                        )
                    )
        except Exception as e:
            raise ServerError(error=InternalError()) from e

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        raise Exception('cancel not supported')


class SummarizerAgent:

    def run(self, port: int):
        url = f'http://0.0.0.0:{port}'
        skill = AgentSkill(
            id='summarize',
            name='Summarize search results in markdown format',
            description='Summarizes search engine results in Markdown format with a brief summary and a table of results.',
            tags=['summarize', 'markdown', 'web'],
        )

        card = AgentCard(
            name='Summarizer Agent',
            description='Summarizes search engine results in Markdown format.',
            url=url,
            version='0.1.0',
            defaultInputModes=['text'],
            defaultOutputModes=['text'],
            capabilities=AgentCapabilities(streaming=True),
            skills=[skill],
            supportsAuthenticatedExtendedCard=False
        )

        request_handler = DefaultRequestHandler(
            agent_executor=SummarizerExecutor(),
            task_store=InMemoryTaskStore()
        )

        server = A2AStarletteApplication(
            agent_card=card,
            http_handler=request_handler,
        )

        uvicorn.run(server.build(), host='0.0.0.0', port=port)


if __name__ == "__main__":
    load_dotenv()
    agent = SummarizerAgent()
    agent.run(port=int(os.getenv('SUMMARIZER_PORT', 8001)))
