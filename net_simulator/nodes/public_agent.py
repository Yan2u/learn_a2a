import argparse
import asyncio
from contextlib import asynccontextmanager
import json
import threading
from asyncio import AbstractEventLoop
from pathlib import Path
from time import sleep

import httpx
import requests
import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryPushNotifier, InMemoryTaskStore
from a2a.types import AgentCard
from starlette.applications import Starlette

import net_simulator.executors as executors
from net_simulator.utils import get_config

CWD = Path(__file__).parent
AGENTS_DIR = CWD.parent / 'config' / 'agents'


class PublicAgent:
    config: dict
    manager_url: str
    agent_id: str
    keep_alive_thread: threading.Thread

    def __init__(self, config_name: str):
        config_file = AGENTS_DIR / f'{config_name}.json'
        if not config_file.exists():
            raise FileNotFoundError(f'Agent {config_name} does not exist')

        self.config = json.load(open(str(config_file), 'r'))

    def _keep_alive(self):
        interval = get_config('system.keep_alive_interval')
        sleep(interval)
        while True:
            response = requests.post(
                f"{self.manager_url}/agents/keepalive",
                json={'agent_id': self.agent_id}
            )
            if response.status_code != 200:
                raise RuntimeError(f"Failed to keep alive: {response.text}")

            sleep(interval)

    def run(self):
        exec_class = self.config['executor']
        if exec_class not in executors.__all__:
            raise ValueError(
                f'Executor {exec_class} is not defined in executors')

        executor = getattr(executors, exec_class)()

        agent_card = AgentCard(
            **self.config['agent_card']
        )

        request_handler = DefaultRequestHandler(
            agent_executor=executor,
            task_store=InMemoryTaskStore(),
            push_notifier=InMemoryPushNotifier(httpx.AsyncClient())
        )

        server = A2AStarletteApplication(
            agent_card=agent_card,
            http_handler=request_handler,
        )

        # register
        self.manager_url = f"http://localhost:{get_config('system.port')}"
        response = requests.post(
            f"{self.manager_url}/agents/register",
            json={'name': self.config['agent_card']['name'],
                  'url': f"http://localhost:{self.config['port']}"}
        )

        if response.status_code != 200:
            raise RuntimeError(f"Failed to register agent: {response.text}")

        response = response.json()
        if response['status'] != 'success':
            raise RuntimeError(
                f"Failed to register agent: {response['message']}")

        self.agent_id = response['agent_id']

        print(F"Registered as {self.agent_id}")

        self.agent_id = response['agent_id']
        self.keep_alive_thread = threading.Thread(
            target=self._keep_alive, daemon=True)
        self.keep_alive_thread.start()

        @asynccontextmanager
        async def app_lifespan(_: Starlette):
            # startup

            # run
            yield

            # shutdown
            try:
                client = httpx.AsyncClient(timeout=5)
                await client.post(
                    f"{self.manager_url}/agents/unregister",
                    json={'agent_id': self.agent_id}
                )
            except Exception as e:
                pass

        uvicorn.run(server.build(lifespan=app_lifespan),
                    host='0.0.0.0', port=self.config['port'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-a', '--agent')

    args = parser.parse_args()

    if args.agent:
        agent = PublicAgent(args.agent)
        agent.run()
    else:
        print('No agent defined')


if __name__ == '__main__':
    main()
