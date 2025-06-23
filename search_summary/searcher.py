import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import TaskState, TextPart, Message
import json

from a2a.client import A2ACardResolver, A2AClient

from a2a.utils import new_agent_text_message

from dotenv import load_dotenv
import os
import bing_searcher


class SearcherExecutor(AgentExecutor):

    def __init__(self):
        pass

    async def execute(self, context: RequestContext, event_queue: EventQueue):
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        if not context.current_task:
            await updater.update_status(TaskState.submitted)
        await updater.update_status(TaskState.working)
        texts = [x.root.text for x in context.message.parts if isinstance(x.root, TextPart)]
        print(texts)
        msg = ' '.join(texts)

        result = await bing_searcher.search(msg)
        if not result:
            await updater.update_status(TaskState.failed)
            return
        await updater.update_status(TaskState.completed)
        await event_queue.enqueue_event(new_agent_text_message(text=json.dumps(result)))

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        raise Exception('cancel not supported')


class SearcherAgent:

    def run(self, port: int):
        url = f'http://0.0.0.0:{port}'
        skill = AgentSkill(
            id='search',
            name='Search https://bing.com/ for given query',
            description='Searches Bing for the given query and returns the results.',
            tags=['search', 'bing', 'web'],
            examples=['google a2a', 'mcp']
        )

        card = AgentCard(
            name='Searcher Agent',
            description='An agent that searches Bing for the given query and returns the results.',
            url=url,
            version='0.1.0',
            defaultInputModes=['text'],
            defaultOutputModes=['text'],
            capabilities=AgentCapabilities(streaming=False),
            skills=[skill],
            supportsAuthenticatedExtendedCard=False
        )

        request_handler = DefaultRequestHandler(
            agent_executor=SearcherExecutor(),
            task_store=InMemoryTaskStore()
        )

        server = A2AStarletteApplication(
            agent_card=card,
            http_handler=request_handler,
        )

        uvicorn.run(server.build(), host='0.0.0.0', port=port)


if __name__ == "__main__":
    load_dotenv()
    agent = SearcherAgent()
    agent.run(port=int(os.getenv('SEARCHER_PORT', 8000)))
