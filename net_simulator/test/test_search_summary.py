import asyncio
import json

import httpx
from a2a.client import A2AClient
from a2a.types import SendMessageRequest, MessageSendParams, SendMessageSuccessResponse, JSONRPCErrorResponse, TextPart
from fastmcp import Client
from openai import AsyncOpenAI
from uuid import uuid4
from net_simulator.utils import get_config, tool_dict, OpenAIService
from pathlib import Path
import base64

CWD = Path(__file__).parent
BASE_URL = 'http://localhost:8100'


async def main():
    user_prompt = input('Search & Summary> ')
    img_b64 = base64.b64encode(open(str(CWD / 'niko_iem.png'), 'rb').read()).decode()
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=360) as httpx_client:
        client = await A2AClient.get_client_from_agent_card_url(httpx_client=httpx_client, base_url=BASE_URL)

        message_dict = {
            'message': {
                'role': 'user',
                'parts': [
                    {'kind': 'text', 'text': user_prompt},
                    # {'kind': 'file', 'file': {'bytes': img_b64}}
                ],
                'messageId': uuid4().hex
            }
        }

        message = SendMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(**message_dict),
        )

        response = (await client.send_message(message)).root
        if isinstance(response, JSONRPCErrorResponse):
            print(response)
        else:
            for artifact in response.result.artifacts:
                print(f"{'Name:':<20}{artifact.name}")
                for part in artifact.parts:
                    if isinstance(part.root, TextPart):
                        print(f"{'Text:':<20}{part.root.text}")
            print(f"{'State:':<20}{response.result.status.state}")

        print(response.model_dump_json(indent=2))


if __name__ == '__main__':
    asyncio.run(main())
