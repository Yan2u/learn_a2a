import uuid

import uvicorn
import httpx
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore, InMemoryPushNotifier
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill, Artifact, TaskArtifactUpdateEvent,
)

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import TaskState, TextPart, Message
import json

from a2a.client import A2ACardResolver, A2AClient

from a2a.utils import new_agent_text_message, new_task, new_text_artifact

from dotenv import load_dotenv
import os
import asyncio


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

        await updater.start_work(new_agent_text_message(
            text='Start straming...',
            context_id=task.contextId,
            task_id=task.id
        ))

        artifact_id = str(uuid.uuid4())
        for i in range(10):
            print(f"[Server] Streaming part {i + 1} of 10")
            append_artifact = True if i > 0 else False

            await event_queue.enqueue_event(
                TaskArtifactUpdateEvent(
                    append=append_artifact,
                    contextId=task.contextId,
                    taskId=task.id,
                    lastChunk=False,
                    artifact=Artifact(
                        name='streaming_part',
                        parts=[TextPart(text=f"Streaming part {i + 1} of 10")],
                        artifactId=artifact_id,
                    )
                )
            )
            await updater.update_status(
                TaskState.working
            )

            await asyncio.sleep(0.5)

        await event_queue.enqueue_event(
            TaskArtifactUpdateEvent(
                append=False,
                contextId=task.contextId,
                taskId=task.id,
                lastChunk=True,
                artifact=new_text_artifact(
                    name='streaming_part',
                    text='Streaming completed.'
                )
            )
        )
        await updater.complete()

    async def cancel(self, context, event_queue):
        raise NotImplementedError(
            "Cancel not supported for MultiTurnExecutor")


class MultiTurnAgent:

    def run(self, port: int):
        url = f'http://127.0.0.1:{port}'
        skill = AgentSkill(
            name='MultiTurn Skill with Streaming',
            id='multiturn_skill_streaming',
            description='A skill that supports multi-turn conversations.',
            tags=['multiturn', 'streaming'],
        )

        card = AgentCard(
            name='MultiTurn Streaming Agent',
            description='An agent that can handle multi-turn conversations with streaming support.',
            url=url,
            version='1.0.0',
            capabilities=AgentCapabilities(
                streaming=True
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
    agent.run(port=8006)
