import uvicorn
from dotenv import load_dotenv
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    SendMessageRequest,
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
import base64
import json


PROMPT = 'What is in this picture? Please describe it in detail.'


async def test_image_descriptor():
    load_dotenv()

    image_descriptor_httpx = httpx.AsyncClient(base_url=f"http://localhost:{os.getenv('IMAGE_DESCRIPTOR_PORT', 8003)}", timeout=360)
    image_descriptor_card = await A2ACardResolver(httpx_client=image_descriptor_httpx, base_url=f"http://localhost:{os.getenv('IMAGE_DESCRIPTOR_PORT', 8003)}").get_agent_card()
    image_descriptor_client = A2AClient(httpx_client=image_descriptor_httpx, agent_card=image_descriptor_card)

    message_dict = {
        'message': {
            'role': 'user',
            'parts': [
                {'kind': 'file', 'file': {'bytes': base64.b64encode(open('test.jpg', 'rb').read()).decode('utf-8')}},
                {'kind': 'text', 'text': 'jpg'},
                {'kind': 'text', 'text': 'Describe this image in detail.'}
            ],
            'messageId': uuid4().hex,
        }
    }

    message = SendStreamingMessageRequest(
        id=str(uuid4()),
        params=MessageSendParams(**message_dict)
    )

    response = image_descriptor_client.send_message_streaming(message)

    async for chunk in response:
        if chunk.root.result.status.message:
            print(chunk.root.result.status.message.parts[0].root.text, end='', flush=True)


async def test_speech2text():
    load_dotenv()

    speech2text_httpx = httpx.AsyncClient(base_url=f"http://localhost:{os.getenv('SPEECH2TEXT_PORT', 8004)}", timeout=360)
    speec2text_card = await A2ACardResolver(httpx_client=speech2text_httpx, base_url=f"http://localhost:{os.getenv('SPEECH2TEXT_PORT', 8004)}").get_agent_card()
    speech2text_client = A2AClient(httpx_client=speech2text_httpx, agent_card=speec2text_card)

    message_dict = {
        'message': {
            'role': 'user',
            'parts': [
                {'kind': 'file', 'file': {'bytes': base64.b64encode(open('test.wav', 'rb').read()).decode('utf-8')}},
            ],
            'messageId': uuid4().hex,
        }
    }

    message = SendMessageRequest(
        id=str(uuid4()),
        params=MessageSendParams(**message_dict)
    )

    response = await speech2text_client.send_message(message)

    if response.root.result:
        for history in response.root.result.history:
            if history.parts and history.parts[0].root.kind == 'text':
                print(history.parts[0].root.text, end='', flush=True)

    if response.root.result.status.message:
        print(response.root.result.status.message.parts[0].root.text)
    else:
        print("No transcription received.")


async def main():
    load_dotenv()

    user_agent_httpx = httpx.AsyncClient(
        base_url=f"http://localhost:{os.getenv('USER_PORT', 8005)}",
        timeout=360
    )
    user_agent_card = await A2ACardResolver(httpx_client=user_agent_httpx, base_url=f"http://localhost:{os.getenv('USER_PORT', 8005)}").get_agent_card()
    user_agent_client = A2AClient(httpx_client=user_agent_httpx, agent_card=user_agent_card)

    img_b64 = base64.b64encode(open('test.jpg', 'rb').read()).decode('utf-8')

    print(f"[Test] Using plain text prompt: {PROMPT}")
    message_dict = {
        'message': {
            'role': 'user',
            'parts': [
                {'kind': 'file', 'file': {'bytes': img_b64}},
                {'kind': 'text', 'text': PROMPT}
            ],
            'messageId': uuid4().hex,
        }
    }
    message = SendStreamingMessageRequest(
        id=str(uuid4()),
        params=MessageSendParams(**message_dict)
    )
    stream = user_agent_client.send_message_streaming(message)
    async for chunk in stream:
        if chunk.root.result.status.message:
            print(chunk.root.result.status.message.parts[0].root.text, end='', flush=True)

    print('\n\n[TestClient] Using audio prompt:', flush=True)
    wav_b64 = base64.b64encode(open('test.wav', 'rb').read()).decode('utf-8')
    message_dict = {
        'message': {
            'role': 'user',
            'parts': [
                {'kind': 'file', 'file': {'bytes': img_b64}},
                {'kind': 'file', 'file': {'bytes': wav_b64}},
            ],
            'messageId': uuid4().hex,
        }
    }

    message = SendMessageRequest(
        id=str(uuid4()),
        params=MessageSendParams(**message_dict)
    )

    # [WARN] cannot use streaming here because the speech2text agent is not streaming
    #
    # stream = user_agent_client.send_message_streaming(message, http_kwargs={'timeout': 360})
    # async for chunk in stream:
    #     if chunk.root.result.status.message:
    #         print(chunk.root.result.status.message.parts[0].root.text, end='', flush=True)

    response = await user_agent_client.send_message(message, http_kwargs={'timeout': 360})
    if response.root.result:
        for history in response.root.result.history:
            if history.parts and history.parts[0].root.kind == 'text':
                print(history.parts[0].root.text, end='', flush=True)

    if response.root.result.status.message:
        print(response.root.result.status.message.parts[0].root.text)


if __name__ == "__main__":
    asyncio.run(main())
    # asyncio.run(test_image_descriptor())
    # asyncio.run(test_speech2text())
