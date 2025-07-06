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

from openai import AsyncOpenAI

N_TASKS = 12
SEARCH_KEYWORDS = [
    'google a2a',
    'python async programming',
    'dotnet 9.0',
    'react vs vue',
    'kubernetes tutorial',
    'transformers nlp',
    'mcp protocol',
    'asgi',
    'ffmpeg',
    'gemini 2.5 pro',
    'gpt o3',
    'deepseek r1 0528'
]


async def client_task(keyword: str = ''):
    async with httpx.AsyncClient(base_url=f"http://localhost:{os.getenv('SEARCHER_PORT', 8001)}",
                                 timeout=360) as client:
        searcher_card = await A2ACardResolver(httpx_client=client,
                                              base_url=f"http://localhost:{os.getenv('SEARCHER_PORT', 8001)}").get_agent_card()
        searcher_client = A2AClient(
            httpx_client=client, agent_card=searcher_card)

        message_dict = {
            'message': {
                'role': 'user',
                'parts': [
                    {'kind': 'text', 'text': keyword}
                ],
                'messageId': uuid4().hex,
            },
        }

        message = SendMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(**message_dict)
        )

        response = await searcher_client.send_message(message)

        print(f"Result for `{keyword}` ========================")
        result_j = json.loads(
            response.root.result.artifacts[0].parts[0].root.text)
        print(result_j)
        print()


async def main():
    # load_dotenv()
    # tasks = [client_task(SEARCH_KEYWORDS[i]) for i in range(N_TASKS)]
    # await asyncio.gather(*tasks)

    client = AsyncOpenAI(
        api_key='',
        base_url='https://api.siliconflow.cn/v1',
    )

    response = await client.chat.completions.create(
        messages=[
            {'role': 'system', 'content': 'You are a helpful assistant.'},
            {'role': 'user', 'content': 'What is LLM?'}
        ],
        model='Qwen/Qwen2.5-7B-Instruct'
    )

    print(response.choices[0].message.content)


if __name__ == "__main__":
    asyncio.run(main())
