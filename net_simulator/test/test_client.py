import asyncio
from uuid import uuid4

import httpx
from a2a.client import A2AClient
from a2a.types import SendMessageRequest, MessageSendParams

BASE_URL = 'http://localhost:8100'


async def main():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=360) as client:
        a2aclient = await A2AClient.get_client_from_agent_card_url(
            httpx_client=client,
            base_url=BASE_URL,
        )

        message_dict = {
            'message': {
                'role': 'user',
                'parts': [
                    {'kind': 'text', 'text': 'Yan2u'}
                ],
                'messageId': uuid4().hex
            }
        }

        message = SendMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(**message_dict)
        )

        response = await a2aclient.send_message(message)
        print(response.model_dump_json(indent=2))


if __name__ == '__main__':
    asyncio.run(main())
