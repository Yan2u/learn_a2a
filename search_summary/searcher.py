import uvicorn
import httpx
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore, InMemoryPushNotifier
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

from a2a.utils import new_agent_text_message, new_task

from dotenv import load_dotenv
import os
import bing_searcher


class SearcherExecutor(AgentExecutor):

    def __init__(self):
        pass

    async def execute(self, context: RequestContext, event_queue: EventQueue):
        task = context.current_task
        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.contextId)
        query = context.get_user_input(delimiter=' ')
        print(query)

        await updater.start_work(new_agent_text_message(
            text='Starting search for: ' + query,
            context_id=context.context_id,
            task_id=context.task_id
        ))

        result = await bing_searcher.search(query.replace(' ', '+'))
        if not result:
            await updater.failed(new_agent_text_message(
                text='No results found for: ' + query,
                context_id=context.context_id,
                task_id=context.task_id
            ))
            return
        await updater.add_artifact(
            name='Search Results',
            parts=[TextPart(text=json.dumps(result, indent=2))],
        )
        await updater.complete()
        print(f"Completed search for: {query}")

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        raise Exception('cancel not supported')


class SearcherAgent:

    def run(self, port: int):
        url = f'http://127.0.0.1:{port}'
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
            task_store=InMemoryTaskStore(),
            push_notifier=InMemoryPushNotifier(httpx.AsyncClient())
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
