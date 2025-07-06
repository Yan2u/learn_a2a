import uvicorn
import json
from dotenv import load_dotenv
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    SendMessageRequest,
    GetTaskRequest,
    SendStreamingMessageRequest,
    TaskState,
    TextPart,
    MessageSendParams,
    Message
)
from a2a.client import A2AClient, A2ACardResolver
from a2a.server.tasks import TaskUpdater
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message
import httpx
import os
from uuid import uuid4
import asyncio


async def test_multiturn():
    async with httpx.AsyncClient(base_url='http://localhost:8005', timeout=360) as client:
        searcher_card = await A2ACardResolver(httpx_client=client, base_url='http://localhost:8005').get_agent_card()
        a2a_client = A2AClient(
            httpx_client=client, agent_card=searcher_card)

        message_dict = {
            'message': {
                'role': 'user',
                'parts': [{'kind': 'text', 'text': '123'}],
                'messageId': uuid4().hex,
            },
        }
        message = SendMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(**message_dict)
        )

        response = await a2a_client.send_message(message)

        print('Initial turn:')
        print(response.model_dump_json(indent=2))

        task_id = response.root.result.id
        context_id = response.root.result.contextId

        print(f'Task ID: {task_id}, Context ID: {context_id}')

        message_dict = {
            'message': {
                'role': 'user',
                'parts': [{'kind': 'text', 'text': '456'}],
                'messageId': uuid4().hex,
                'taskId': task_id,
                'contextId': context_id,
            },
        }

        message = SendMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(**message_dict)
        )

        response = await a2a_client.send_message(message)

        print('Second turn:')
        print(response.model_dump_json(indent=2))


async def test_multiturn_streaming():
    async with httpx.AsyncClient(base_url='http://localhost:8006', timeout=360) as client:
        agent_card = await A2ACardResolver(httpx_client=client, base_url='http://localhost:8006').get_agent_card()
        a2a_client = A2AClient(
            httpx_client=client, agent_card=agent_card)

        message_dict = {
            'message': {
                'role': 'user',
                'parts': [{'kind': 'text', 'text': '123'}],
                'messageId': uuid4().hex,
            },
        }
        message = SendStreamingMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(**message_dict)
        )

        response = a2a_client.send_message_streaming(message)

        print(f"[Client] Test straming response...")
        i = 0
        async for chunk in response:
            print(f"Chunk #{i}: ===============================", flush=True)
            print(chunk.model_dump_json(indent=2), flush=True)
            i += 1

        print(f"[Client] Test non-streaming response...")

        message = SendMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(**message_dict)
        )

        response = await a2a_client.send_message(message)

        print(response.model_dump_json(indent=2))


async def main():
    await test_multiturn()
    # await test_multiturn_streaming()


if __name__ == '__main__':
    load_dotenv()
    asyncio.run(main())
