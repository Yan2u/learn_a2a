import asyncio
from uuid import uuid4
import httpx
import json
from net_simulator.utils import get_config


async def main():
    client = httpx.AsyncClient(timeout=60)

    user_id = str(uuid4())
    convo_id = str(uuid4())

    response = await client.post(
        f"http://localhost:{get_config('system.port')}/user/register",
        json={
            'user_id': user_id,
        }
    )

    if response.status_code != 200:
        print(f"Failed to register user: {response.text}")
        return

    print(f"User registered with ID: {user_id}")

    response = await client.post(
        f"http://localhost:{get_config('system.port')}/user/chat",
        json={
            'user_id': user_id,
            'conversation_id': convo_id,
            'message': 'Search esports team Team Vitality. Plain text format.'
        }
    )

    if response.status_code != 200:
        print(f"Failed to send chat message: {response.text}")
        return

    print("======================================")
    print(json.dumps(response.json(), indent=2))
    print("======================================")

    response = await client.get(
        f"http://localhost:{get_config('system.port')}/events/get/tasks/{user_id}"
    )

    if response.status_code != 200:
        print(f"Failed to get messages: {response.text}")
        return

    print("======================================")
    print(json.dumps(response.json(), indent=2))
    print("======================================")

    response = await client.get(
        f"http://localhost:{get_config('system.port')}/events/get/artifacts/{user_id}"
    )

    if response.status_code != 200:
        print(f"Failed to get messages: {response.text}")
        return

    print("======================================")
    print(json.dumps(response.json(), indent=2))
    print("======================================")

if __name__ == '__main__':
    asyncio.run(main())
