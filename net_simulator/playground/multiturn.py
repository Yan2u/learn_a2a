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


class MultiTurnExecutor(AgentExecutor):

    async def execute(self, context: RequestContext, event_queue: EventQueue):
        task = context.current_task
        if not task:
            print('Creating new task for context:', context.context_id)
            task = new_task(context.message)
            await event_queue.enqueue_event(task)
        else:
            print(f"Existing task {task.id}, status: {task.status.state}")

        print(f"User Input: {context.get_user_input(delimiter=' ')}")

        updater = TaskUpdater(event_queue, task.id, task.contextId)

        if task.status.state != TaskState.working:
            await updater.add_artifact(
                name='Starting Artifact',
                parts=[TextPart(text='Start!')]
            )
            await updater.start_work(new_agent_text_message(
                text='Start Working...',
                context_id=context.context_id,
                task_id=context.task_id
            ))
        else:
            await updater.add_artifact(
                name='Working Artifact',
                parts=[TextPart(text='Working!')]
            )
            await updater.update_status(TaskState.working,
                                        new_agent_text_message(
                                            text='Continuing work...',
                                            context_id=context.context_id,
                                            task_id=context.task_id
                                        ))

    async def cancel(self, context, event_queue):
        raise NotImplementedError(
            "Cancel not supported for MultiTurnExecutor")


class MultiTurnAgent:

    def run(self, port: int):
        url = f'http://127.0.0.1:{port}'
        skill = AgentSkill(
            id='multiturn',
            name='MultiTurn Skill',
            description='A skill that allows multi-turn interactions with the agent.',
            tags=['multi-turn', 'conversation'],
        )

        card = AgentCard(
            name='MultiTurn Agent',
            description='An agent that can handle multi-turn conversations.',
            url=url,
            version='1.0.0',
            capabilities=AgentCapabilities(
                streaming=False
            ),
            defaultInputModes=['text'],
            defaultOutputModes=['text'],
            skills=[skill],
            baseUrl=url,
            supportsAuthenticatedExtendedCard=False
        )

        request_handler = DefaultRequestHandler(
            agent_executor=MultiTurnExecutor(),
            task_store=InMemoryTaskStore(),
            push_notifier=InMemoryPushNotifier(httpx.AsyncClient())
        )

        server = A2AStarletteApplication(
            agent_card=card,
            http_handler=request_handler,
        )

        uvicorn.run(server.build(), host='0.0.0.0', port=port)


if __name__ == '__main__':
    agent = MultiTurnAgent()
    agent.run(port=8005)
