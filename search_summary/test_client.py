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

QUERY = 'google a2a'


async def main():
    load_dotenv()
    print(f"[search_summary] Search and summarize in markdown: {QUERY}")
    async with httpx.AsyncClient(base_url=f"http://localhost:{os.getenv('ORCHESTRATOR_PORT', 8002)}", timeout=1800) as client:
        orchestrator_card = await A2ACardResolver(httpx_client=client, base_url=f"http://localhost:{os.getenv('ORCHESTRATOR_PORT', 8002)}").get_agent_card()
        orchestrator_client = A2AClient(
            httpx_client=client, agent_card=orchestrator_card)

        message_dict = {
            'message': {
                'role': 'user',
                'parts': [
                    {'kind': 'text', 'text': QUERY}
                ],
                'messageId': uuid4().hex,
            },
        }

        message = SendStreamingMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(**message_dict)
        )

        response = orchestrator_client.send_message_streaming(message)
        async for chunk in response:
            if chunk.root.result.status.message:
                print(
                    chunk.root.result.status.message.parts[0].root.text, end='', flush=True)

if __name__ == "__main__":
    asyncio.run(main())
