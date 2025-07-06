from argparse import ArgumentParser
from asyncio import tasks
import json
import logging
from typing import List, Literal
import httpx
import requests
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from typing_extensions import Annotated
from pydantic import Field
from net_simulator.msgs import AgentRegistryInfo
from net_simulator.utils import get_config
import sys
from a2a.client import A2ACardResolver, A2AClient
from a2a.types import Part, TextPart, FilePart, SendMessageRequest, SendStreamingMessageRequest, MessageSendParams, Task, TaskStatusUpdateEvent, TaskArtifactUpdateEvent, GetTaskRequest, TaskQueryParams, JSONRPCErrorResponse
from uuid import uuid4


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
            if isinstance(event, Task):
                url = f"http://localhost:{get_config('system.port')}/events/task/{self.agent_id}"
            elif isinstance(event, TaskStatusUpdateEvent):
                url = f"http://localhost:{get_config('system.port')}/events/task_status/{self.agent_id}"
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

    async def _user_send_messages(self, agent_url: str, parts: List[Part]) -> dict:
        async with httpx.AsyncClient(base_url=agent_url, timeout=360) as httpx_client:
            client = await A2AClient.get_client_from_agent_card_url(
                httpx_client=httpx_client,
                base_url=agent_url
            )

            message_dict = {
                'message': {
                    'role': 'user',
                    'parts': parts,
                    'messageId': uuid4().hex,
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

    async def _agent_send_messages(self, agent_url: str, parts: List[Part]) -> dict:
        async with httpx.AsyncClient(base_url=agent_url, timeout=360) as httpx_client:
            client = await A2AClient.get_client_from_agent_card_url(
                httpx_client=httpx_client,
                base_url=agent_url
            )

            message_dict = {
                'message': {
                    'role': 'user',
                    'parts': parts,
                    'messageId': uuid4().hex,
                }
            }

            message = SendMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(**message_dict)
            )

            response = await client.send_message(message)
            if isinstance(response.root, JSONRPCErrorResponse):
                raise ToolError(
                    f"Error from agent: {response.root.error}")

            result = response.root.result
            return result.model_dump()

    async def _get_public_agents(self) -> List[AgentRegistryInfo]:
        """
        Get all public agents registered with the MCP manager.
        Returns a list of AgentRegistryInfo objects.
        """
        manager_url = f"http://localhost:{get_config('system.port')}"
        try:
            async with httpx.AsyncClient(base_url=manager_url, timeout=10) as client:
                response = await client.get('/agents/all')
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
                description='List of parts to send to the agent. A list of TextPart and FilePart(FileWithBytes) is expected.')]
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
                {'kind' : 'file', 'file': {'bytes': '<Your base64 encoded picture bytes>'}} // <-- a FilePart with kind=file. 
                // NOTE: This json format must be strictly followed, or your request will fail.
            ]

            Returns a JSON object that describes the task that was created by the agent.
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
                        }
                    )
                    if response.status_code != 200 or response.json()['status'] == 'error':
                        raise ToolError(
                            f"Failed to start interaction with agent {target}. Status code {response.status_code}: {response.text}")

                    result = None
                    if self.role == 'user':
                        result = await self._user_send_messages(agent_url, parts)
                    elif self.role == 'agent':
                        result = await self._agent_send_messages(agent_url, parts)
                    else:
                        raise ToolError(
                            f"Invalid role: {self.role}. Expected 'user' or 'agent'.")

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
