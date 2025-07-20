import logging
from argparse import ArgumentParser
from datetime import datetime
from typing import List, Literal
from uuid import uuid4

import httpx
import requests
from a2a.client import A2ACardResolver, A2AClient
from a2a.types import (GetTaskRequest, JSONRPCErrorResponse, MessageSendParams,
                       Part, SendMessageRequest, SendStreamingMessageRequest,
                       Task, TaskArtifactUpdateEvent, TaskQueryParams,
                       TaskStatusUpdateEvent)

from a2a.utils import get_text_parts
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field
from typing_extensions import Annotated

from net_simulator.datamodels import StampedTask
from net_simulator.msgs import AgentRegistryInfo
from net_simulator.utils import get_config
from pathlib import Path
import json

CWD = Path(__file__).parent


class AgentService:

    agent_id: str
    role: Literal['agent', 'user']

    def __init__(self, agent_id: str, role: str):
        self.agent_id = agent_id
        self.role = role

    async def _update_event(self, event: Task | TaskStatusUpdateEvent | TaskArtifactUpdateEvent):
        client = httpx.AsyncClient()
        try:
            url = ''
            response = None
            if isinstance(event, Task):
                url = f"http://localhost:{get_config('system.port')}/events/task/{self.agent_id}"
                response = await client.post(
                    url,
                    json={
                        'timestamp': datetime.now().isoformat(),
                        **event.model_dump(),
                    }
                )
            elif isinstance(event, TaskStatusUpdateEvent):
                url = f"http://localhost:{get_config('system.port')}/events/task_status/{self.agent_id}"
                response = await client.post(
                    url,
                    json=event.model_dump()
                )
            elif isinstance(event, TaskArtifactUpdateEvent):
                url = f"http://localhost:{get_config('system.port')}/events/task_artifact/{self.agent_id}"
                response = await client.post(
                    url,
                    json=event.model_dump()
                )

            if response.status_code != 200:
                raise ToolError(
                    f"Failed to update event. Status code {response.status_code}: {response.text}")
            response = response.json()
            if response['status'] == 'error':
                raise ToolError(
                    f"Failed to update event: {response['message']}")
        except Exception as e:
            raise ToolError from e

        await client.aclose()

    async def _send_messages(self, agent_url: str, parts: List[Part], task_id: str | None = None, context_id: str | None = None) -> dict:
        async with httpx.AsyncClient(base_url=agent_url, timeout=1800) as httpx_client:
            client = await A2AClient.get_client_from_agent_card_url(
                httpx_client=httpx_client,
                base_url=agent_url
            )

            message_dict = {
                'message': {
                    'role': 'user',
                    'parts': parts,
                    'messageId': uuid4().hex,
                    'taskId': task_id,
                    'contextId': context_id,
                }
            }

            message = SendStreamingMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(**message_dict)
            )

            response = client.send_message_streaming(message)
            task_id = None

            async for event in response:
                if isinstance(event.root, JSONRPCErrorResponse):
                    raise ToolError(
                        f"Error from agent: {event.root.error}")

                result = event.root.result

                if isinstance(result, (Task, TaskStatusUpdateEvent, TaskArtifactUpdateEvent)):
                    task_id = result.id if isinstance(
                        result, Task) else result.taskId
                    await self._update_event(result)

            get_task_req = GetTaskRequest(
                id=uuid4().hex,
                params=TaskQueryParams(id=task_id)
            )

            task = await client.get_task(get_task_req)
            return task.model_dump()

    async def _get_public_agents(self) -> List[AgentRegistryInfo]:
        """
        Get all public agents registered with the MCP manager.
        Returns a list of AgentRegistryInfo objects.
        """
        manager_url = f"http://localhost:{get_config('system.port')}"
        try:
            async with httpx.AsyncClient(base_url=manager_url, timeout=10) as client:
                response = await client.post('/agents/discover', json={'agent_id': self.agent_id})
                if response.status_code != 200:
                    raise ToolError(
                        f"Failed to get public agents. Status code {response.status_code}: {response.text}")

                response = response.json()
                if response['status'] == 'error':
                    raise ToolError(
                        f"Failed to get public agents: {response['message']}")

                agents = response['content']
                return [AgentRegistryInfo(**agent) for agent in agents]
        except Exception as e:
            raise ToolError from e

    def run(self):
        mcp = FastMCP(
            name='Agent Service',
            instructions='Userful tools for discovering and commnunicating with agents in the agent network.')

        @mcp.tool(name='agent_discover')
        async def agent_discover() -> List[dict]:
            """
            Discover all agents registered with the MCP manager.
            Returns a JSON that describes all agents (URL, Skills, Capabilities, etc.).
            """

            try:
                agents = await self._get_public_agents()

                result = []
                for agent in agents:
                    async with httpx.AsyncClient(timeout=10) as agent_httpx_client:
                        agent_card = await A2ACardResolver(
                            httpx_client=agent_httpx_client,
                            base_url=agent.url
                        ).get_agent_card()
                        result.append({
                            'url': agent.url,
                            'name': agent.name,
                            'card': agent_card.model_dump()
                        })

            except Exception as e:
                raise ToolError from e

            return result

        @mcp.tool(name='agent_send_message')
        async def agent_send_message(
            agent_url: Annotated[str, Field(description='URL of the agent to send the message to')],
            parts: Annotated[List[Part], Field(
                description='List of parts to send to the agent. A list of TextPart and FilePart(FileWithBytes) is expected.')],
            task_id: Annotated[str | None, Field(description='Task ID to associate with the message, if any. Can be None or omitted.', default=None)],
            context_id: Annotated[str | None, Field(description='Context ID to associate with the message, if any. Can be None or omitted.', default=None)],
        ) -> dict:
            """
            Send a message to an agent with URL `agent_url`. You can get url from calling `agent_discover` tool.
            The `parts` is a list of parts to send to the agent. It can contain text messages or files (bytes).
            Examples of parts are listed below:

            1.
            [
                {'kind' : 'text', 'text': 'Hello, agent!'} // <-- this is a TextPart, with kind=text
            ]

            2.
            [
                {'kind' : 'text', 'text': 'What is in this picture?'}
                {'kind' : 'file', 'file': {'bytes': '<ID of this file in the file system>'} // <-- a FilePart with kind=file. 
                // NOTE: This json format must be strictly followed, or your request will fail.
            ]

            Currently, use `'kind': 'file'` only when you want to pass an image to the agent.

            ID OF THE FILE:

            You can know the ID of the file from both users and other agents. When you want to send this file to another agent, you should pass the ID of the file in the `bytes` field. It is automatically replace by file system.
            For example, you can suppose that the file system is:
            {
                'abc123abc' : {
                    'type' : 'image/jpeg',
                    'data' : '<base64 encoded image data>'
                }
            }

            Then you just pass

            {
                'kind': 'file',
                'file': {
                    'bytes': 'abc123abc'
                }
            }

            It will be

            {
                'kind': 'file',
                'file': {
                    'mimeType': 'image/jpeg',
                    'bytes': '<base64 encoded image data>'
                }
            }

            You should tell others about the ID of the file at the same time you send them files, so they can use it in their requests.
            For example: "Please help me analyze this image. The ID of the image is abc123abc. You can use it in your requests to other agents."

            You must STRICTLY follow the JSON format or the request will FAIL.

            This will return a JSON object that describes the task that was created by the agent.

            PARAMETERS:

            - agent_url: the URL of the agent to send the message to. You can get this URL from calling `agent_discover` tool.
            - parts: a list of parts to send to the agent. It can contain text messages or files (bytes). Examples of parts are listed above.
            - task_id: **WHEN TO USE**: some tasks may not be completed in one turn (you may receive a JSON object with `status: need_input`). You need to keep the id of the unfinished task, and pass it to this parameter when you want to continue the task. If you don't have a task ID, you can omit this parameter or set it to None. This means a new task will be created.
            - context_id: **WHEN TO USE**: a context is of higher level of a task and it can contain multiple tasks. If you want to associate the message with a context, you can pass the context ID here. If you don't have a context ID, you can omit this parameter or set it to None. This means a new context will be created.

            NOTE: This tool may take a long time to complete, depending on the agent's processing time.
            """

            try:
                manager_url = f"http://localhost:{get_config('system.port')}"
                agents = await self._get_public_agents()
                target = ''
                for agent in agents:
                    if agent.url == agent_url:
                        target = agent.agent_id
                        break
                if not target:
                    raise ToolError(
                        f"Agent with URL {agent_url} not found in the agent registry.")
                async with httpx.AsyncClient(base_url=manager_url, timeout=10) as client:
                    # start interaction
                    response = await client.post(
                        '/interactions/add',
                        json={
                            'src_id': self.agent_id,
                            'dst_id': target,
                            'message': '\n'.join(get_text_parts(parts))
                        }
                    )
                    if response.status_code != 200 or response.json()['status'] == 'error':
                        raise ToolError(
                            f"Failed to start interaction with agent {target}. Status code {response.status_code}: {response.text}")

                    result = await self._send_messages(agent_url, parts, task_id, context_id)

                    # end interaction
                    await client.post(
                        '/interactions/delete',
                        json={
                            'src_id': self.agent_id,
                            'dst_id': target,
                        }
                    )

                    return result
            except Exception as e:
                raise ToolError from e

        @mcp.tool(name='search_web')
        def search_web(
                query: Annotated[str, Field(description='query to search for in the web')],
                count: Annotated[
                    int, Field(description='number of results to return, must be 1 to 10, default=10', default=10)],
        ) -> List[dict]:
            """
            Search the web for given query. Returns results in JSON format.
            Each result includes:
            1) name, 2) URL, 3) a brief snippet of the webpage, 4) a brief summary of the webpage,
            5) date of publication (maybe N/A if not available).
            """

            api_key = get_config('langsearch_api_key')

            response = requests.post(
                url='https://api.langsearch.com/v1/web-search',
                json={
                    'query': query,
                    'freshness': 'noLimit',
                    'summary': True,
                    'count': count
                },
                headers={
                    'Authorization': f"Bearer {api_key}"
                }
            )

            if response.status_code != 200:
                raise ToolError(
                    f"Search failed. Status code {response.status_code}: {response.text}")

            return response.json()['data']['webPages']['value']

        mcp.run()


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-r', '--role', type=str, default='agent',
                        choices=['agent', 'user'], required=True,
                        help='Role of the service, either "agent" or "user".')
    parser.add_argument('-i', '--id', type=str, required=True,
                        help='ID to register with the agent service mcp. Represents the user ID or agent ID in the agent network.')

    args = parser.parse_args()

    service = AgentService(agent_id=args.id, role=args.role)
    logger = logging.getLogger(__file__)
    logger.info(f"AgentService(id={args.id}, role={args.role}) started...")
    service.run()
