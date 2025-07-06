import asyncio
from contextlib import asynccontextmanager
import logging
import time
from typing import Any, Dict, List, Literal, Tuple

import fastapi
from pydantic import BaseModel
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastmcp.client.transports import PythonStdioTransport

from net_simulator.msgs import (ErrorResponse, ResponseT,
                                TextResponse, UserChatRequest,
                                UserConversationsResponse, UserMessageResponse,
                                UserRegisterRequest, AgentRegistryRequest, AgentRegistryResponse, AgentKeepAliveRequest, AgentRegistryInfo,
                                AgentInteractionAddRequest, AgentTaskCountAddRequest)

from net_simulator.utils import OpenAIService, SiliconFlowService, get_config, get_llm
from a2a.types import Task, TaskStatusUpdateEvent, TaskArtifactUpdateEvent, Artifact

from uuid import uuid4

SYSTEM_PROMPT = """Now you are a personal assistant for users. Your responsibility is: for the needs put forward by users, use the Agent Service tool to discover, find and decide on suitable Agents in the Agent Network to handle users' work. If the user's needs are relatively complex, you may need to divide the task and call multiple Agents to complete this task.

**The role you play is "the organizer of the team and the planner of the task".**

**Please keep in mind: in principle, you cannot handle the user's needs by yourself. Instead, you need to analyze the user's needs, combine the existing Agents in the Agent Network, and send messages to them to complete the task put forward by the user.**

**Wht you cannot do is**

- Directly handle the user's needs or directly answer the user's questions;
- Try to solve the problem by yourself when there is no Agent in the Agent Network who can do the job;

**What you need to do is**

- Find a suitable Agent for the user's needs and send a message to him (through the Agent Service tool) to solve it;
- If the user's needs are relatively complex, you need to arrange a set of task processing processes, that is, consider how to call multiple Agents and synthesize their results to meet the user's needs.
- If there is no Agent in the Agent Network that can meet the user's needs, you need to honestly explain to the user and ask the user to change the needs.
"""


class AgentNetNode(BaseModel):
    """
    Represents a node in the agent network.
    """

    interactions: List[str] = []
    kind: str


class PublicAgentNode(AgentNetNode):
    """
    Represents a public agent node in the agent network.
    """

    kind: Literal['public'] = 'public'
    task_count: int = 0
    url: str
    lastseen: float
    name: str


class UserAgentNode(AgentNetNode):
    """
    Represents a user agent node in the agent network.
    """

    kind: Literal['user'] = 'user'
    conversations: Dict[str, List[Dict[str, Any]]]
    tasks: Dict[str, Task]


KEEP_ALIVE_THRESHOLD = get_config('system.keep_alive_threshold')  # seconds
KEEP_ALIVE_INTERVAL = get_config('system.keep_alive_interval')  # seconds
PORT = get_config('system.port')  # port for the system


def main():
    logger = logging.getLogger('uvicorn')

    # network graph
    graph: Dict[str, PublicAgentNode | UserAgentNode] = {}

    llm = get_llm()

    # ================================================================================
    # Public agnets registration
    # ================================================================================

    async def keep_alive_check():
        """
        Periodically check if agents are still alive.
        """
        while True:
            current_time = time.time()
            for agent_id, agent in list(graph.items()):
                if agent.kind != 'public':
                    continue
                if current_time - agent.lastseen > KEEP_ALIVE_THRESHOLD:
                    logger.warning(
                        f"Agent({agent_id}) is inactive, removing from registry.")
                    del graph[agent_id]
            await asyncio.sleep(KEEP_ALIVE_INTERVAL)

    @asynccontextmanager
    async def lifespan(_: fastapi.FastAPI):
        """
        Lifespan event to start the keep-alive check.
        """
        asyncio.create_task(keep_alive_check())
        yield

    app = FastAPI(lifespan=lifespan)

    @app.post('/agents/register', status_code=200)
    def agent_register(request: AgentRegistryRequest):
        """
        Register an agent with the manager.
        """

        for _, v in graph.items():
            if v.kind != 'public':
                continue
            if v.url == request.url:
                logger.error(f"Agent({request.url}) already registered.")
                return ErrorResponse(
                    message=f"Agent({request.url}) already registered.",
                )

        agent_id = uuid4().hex
        graph[agent_id] = PublicAgentNode(
            name=request.name,
            url=request.url,
            lastseen=time.time(),
        )

        logger.info(f"Agent({agent_id}) registered.")
        return AgentRegistryResponse(
            agent_id=agent_id,
        )

    @app.post('/agents/keepalive', status_code=200)
    def keep_alive(request: AgentKeepAliveRequest):
        """
        keep alive endpoint for agents to notify the manager that they are still active.
        """

        if request.agent_id not in graph:
            logger.error(f"Agent({request.agent_id}) not found.")
            return ErrorResponse(
                message=f"Agent({request.agent_id}) not found.",
            )

        if graph[request.agent_id].kind != 'public':
            logger.error(f"Agent({request.agent_id}) is not a public agent.")
            return ErrorResponse(
                message=f"Agent({request.agent_id}) is not a public agent.",
            )

        graph[request.agent_id].lastseen = time.time()
        logger.info(f"Agent({request.agent_id}) keep-alive.")
        return TextResponse(content='OK')

    @app.get('/agents/all', status_code=200)
    def get_agents() -> ResponseT[List[AgentRegistryInfo]]:
        """
        get the list of registered agents.
        """

        result = []
        for agent_id, agent in graph.items():
            if agent.kind != 'public':
                continue
            result.append(AgentRegistryInfo(
                agent_id=agent_id,
                name=agent.name,
                url=agent.url,
            ))

        return ResponseT(content=result)

    @app.post('/agents/unregister', status_code=200)
    def unregister_agent(request: AgentKeepAliveRequest):
        """
        Unregister an agent from the manager.
        """
        if request.agent_id not in graph:
            logger.error(f"Agent({request.agent_id}) not found.")
            return ErrorResponse(
                message=f"Agent({request.agent_id}) not found.",
            )

        if graph[request.agent_id].kind != 'public':
            logger.error(f"Agent({request.agent_id}) is not a public agent.")
            return ErrorResponse(
                message=f"Agent({request.agent_id}) is not a public agent.",
            )

        del graph[request.agent_id]
        logger.info(f"Agent({request.agent_id}) unregistered.")
        return TextResponse(content='OK')

    # ===============================================================================
    # Agent Interactions (Network Graph Ablities)
    # ================================================================================

    @app.post('/interactions/add')
    def add_agent_interaction(request: AgentInteractionAddRequest):
        """
        Add an interaction between two agents.
        This is used to build the network graph of agent interactions.
        """

        if request.src_id in graph and request.dst_id in graph:
            src = graph[request.src_id]
            if request.dst_id not in src.interactions:
                src.interactions.append(request.dst_id)
                logger.info(
                    f"Interaction ADD: {request.src_id} -> {request.dst_id}")
            return TextResponse(content='ok')
        else:
            logger.error(
                f"Invalid agent IDs: {request.src_id} or {request.dst_id} not found.")
            return ErrorResponse(
                message=f"Invalid agent IDs: {request.src_id} or {request.dst_id} not found."
            )

    @app.post('/interactions/delete')
    def delete_agent_interaction(request: AgentInteractionAddRequest):
        """
        Delete an interaction between two agents.
        This is used to build the network graph of agent interactions.
        """

        if request.src_id in graph and request.dst_id in graph:
            src = graph[request.src_id]
            if request.dst_id in src.interactions:
                src.interactions.remove(request.dst_id)
                logger.info(
                    f"Interaction DELETE: {request.src_id} -> {request.dst_id}")
            return TextResponse(content='ok')
        else:
            logger.error(
                f"Invalid agent IDs: {request.src_id} or {request.dst_id} not found.")
            return ErrorResponse(
                message=f"Invalid agent IDs: {request.src_id} or {request.dst_id} not found."
            )

    @app.get('/interactions')
    def get_agent_interactions() -> ResponseT[List[Tuple[str, str]]]:
        """
        Get all agent interactions.
        This is used to build the network graph of agent interactions.
        """

        return ResponseT(content=[(src_id, dst_id)
                                  for src_id, v in graph.items() for dst_id in v.interactions])

    @app.post('/task_count/add')
    def agent_task_count_add(request: AgentTaskCountAddRequest):
        """
        Get the task count for an agent.
        This is used to build the network graph of agent interactions.
        """

        if request.agent_id not in graph:
            logger.error(f"Agent({request.agent_id}) not found.")
            return ErrorResponse(
                message=f"Agent({request.agent_id}) not found.",
            )

        if graph[request.agent_id].kind != 'public':
            logger.error(f"Agent({request.agent_id}) is not a public agent.")
            return ErrorResponse(
                message=f"Agent({request.agent_id}) is not a public agent.",
            )

        agent = graph[request.agent_id]
        agent.task_count += 1
        return TextResponse(content='ok')

    @app.post('/task_count/delete')
    def agent_task_count_delete(request: AgentTaskCountAddRequest):
        """
        Delete the task count for an agent.
        This is used to build the network graph of agent interactions.
        """

        if request.agent_id not in graph:
            logger.error(f"Agent({request.agent_id}) not found.")
            return ErrorResponse(
                message=f"Agent({request.agent_id}) not found.",
            )

        if graph[request.agent_id].kind != 'public':
            logger.error(f"Agent({request.agent_id}) is not a public agent.")
            return ErrorResponse(
                message=f"Agent({request.agent_id}) is not a public agent.",
            )

        agent = graph[request.agent_id]
        if agent.task_count > 0:
            agent.task_count -= 1
        return TextResponse(content='ok')

    @app.get('/task_count/{agent_id}')
    def get_agent_task_count(agent_id: str) -> ResponseT[int]:
        """
        Get the task count for an agent.
        This is used to build the network graph of agent interactions.
        """

        if agent_id not in graph:
            logger.error(f"Agent({agent_id}) not found.")
            return ErrorResponse(
                message=f"Agent({agent_id}) not found.",
            )

        if graph[agent_id].kind != 'public':
            logger.error(f"Agent({agent_id}) is not a public agent.")
            return ErrorResponse(
                message=f"Agent({agent_id}) is not a public agent.",
            )

        agent = graph[agent_id]
        return ResponseT(content=agent.task_count)

    @app.get('/task_count')
    def get_all_agent_task_counts() -> ResponseT[Dict[str, int]]:
        """
        Get the task counts for all agents.
        This is used to build the network graph of agent interactions.
        """

        return ResponseT(content={
            agent_id: agent.task_count for agent_id, agent in graph.items() if agent.kind == 'public'
        })

    @app.get('/graph')
    def get_agent_graph() -> ResponseT[Dict[str, PublicAgentNode | UserAgentNode]]:
        """
        Get the entire agent network graph.
        This includes all agents and their interactions.
        """

        return ResponseT(content=graph)

    # ================================================================================
    # Events and updates
    # ================================================================================

    @app.post('/events/task/{user_id}')
    def task_add(user_id: str, request: Task):
        """
        Handle task update requests.
        """

        if not user_id in graph:
            logger.error(f"User {user_id} does not exist.")
            return ErrorResponse(message=f"User {user_id} does not exist.")

        if graph[user_id].kind != 'user':
            logger.error(f"User {user_id} is not a user agent.")
            return ErrorResponse(message=f"User {user_id} is not a user agent.")

        user = graph[user_id]
        user.tasks[request.id] = request

        logger.info(f"Task(id={request.id})")
        return TextResponse(content='ok')

    @app.post('/events/task_status/{user_id}')
    def task_status_update(user_id: str, request: TaskStatusUpdateEvent):
        """
        Handle task update requests.
        """

        if not user_id in graph:
            logger.error(f"User {user_id} does not exist.")
            return ErrorResponse(message=f"User {user_id} does not exist.")

        if graph[user_id].kind != 'user':
            logger.error(f"User {user_id} is not a user agent.")
            return ErrorResponse(message=f"User {user_id} is not a user agent.")

        user = graph[user_id]

        if not request.taskId in user.tasks:
            logger.error(
                f"Task {request.taskId} does not exist for user {user_id}.")
            return ErrorResponse(message=f"Task {request.taskId} does not exist for user {user_id}.")

        task = user.tasks[request.taskId]
        task.status = request.status

        logger.info(
            f"TaskStatusUpdate(id={request.taskId}, state={request.status.state})")
        return TextResponse(content='ok')

    @app.post('/events/task_artifact/{user_id}')
    def task_artifact_update(user_id: str, request: TaskArtifactUpdateEvent):
        """
        Handle task artifact update requests.
        """

        if not user_id in graph:
            logger.error(f"User {user_id} does not exist.")
            return ErrorResponse(message=f"User {user_id} does not exist.")

        if graph[user_id].kind != 'user':
            logger.error(f"User {user_id} is not a user agent.")
            return ErrorResponse(message=f"User {user_id} is not a user agent.")

        user = graph[user_id]

        if not request.taskId in user.tasks:
            logger.error(
                f"Task {request.context_id} does not exist for user {user_id}.")
            return ErrorResponse(message=f"Task {request.context_id} does not exist for user {user_id}.")

        task = user.tasks[request.taskId]

        if request.append:
            if not task.artifacts:
                logger.error(
                    f"Task {request.taskId} has no artifacts to append.")
                return ErrorResponse(message=f"Task {request.taskId} has no artifacts to append.")
            for artifact in task.artifacts:
                if artifact.artifactId == request.artifact.artifactId:
                    artifact.parts.extend(request.artifact.parts)
                    return TextResponse(content='ok')

            logger.error(
                f"Artifact {request.artifact.artifactId} not found in task {request.taskId}.")
            return ErrorResponse(message=f"Artifact {request.artifact.artifactId} not found in task {request.taskId}.")

        if not task.artifacts:
            task.artifacts = []
        task.artifacts.append(request.artifact)

        logger.info(
            f"TaskArtifactUpdate(id={request.taskId}, artifactId={request.artifact.artifactId})")
        return TextResponse(content='ok')

    @app.get('/events/get/tasks/{user_id}')
    def get_tasks(user_id: str) -> ResponseT[Dict[str, Dict[str, Any]]]:
        """
        Retrieve events for a specific user.
        """

        if not user_id in graph:
            logger.error(f"User {user_id} does not exist.")
            return ErrorResponse(message=f"User {user_id} does not exist.")

        if graph[user_id].kind != 'user':
            logger.error(f"User {user_id} is not a user agent.")
            return ErrorResponse(message=f"User {user_id} is not a user agent.")

        user = graph[user_id]

        return ResponseT(
            content={
                k: {
                    'id': v.id,
                    'status': str(v.status.state),
                    'message': v.status.message.model_dump() if v.status.message else None
                } for k, v in user.tasks.items()
            }
        )

    @app.get('/events/get/artifacts/{user_id}')
    def get_artifacts(user_id: str) -> ResponseT[List[Artifact]]:
        """
        Retrieve artifacts for a specific user.
        """

        if not user_id in graph:
            logger.error(f"User {user_id} does not exist.")
            return ErrorResponse(message=f"User {user_id} does not exist.")

        if graph[user_id].kind != 'user':
            logger.error(f"User {user_id} is not a user agent.")
            return ErrorResponse(message=f"User {user_id} is not a user agent.")

        user = graph[user_id]

        artifacts = [
            artifact
            for task in user.tasks.values()
            for artifact in (task.artifacts if task.artifacts else [])
        ]

        return ResponseT(content=artifacts)

    # ============================================================
    # User Services
    # ============================================================

    @app.post('/user/register')
    def user_register(request: UserRegisterRequest):
        """
        Register a user with the server.
        """

        user_id = request.user_id

        if user_id in graph:
            logger.error(f"User {user_id} already registered.")
            return ErrorResponse(message=f"User {user_id} already registered.")

        graph[request.user_id] = UserAgentNode(
            conversations={},
            tasks={}
        )

        logger.info(f"UserRegistered(id={request.user_id})")

        return TextResponse(content='ok')

    @app.post('/user/unregister')
    def user_unregister(request: UserRegisterRequest):
        """
        Unregister a user from the server.
        """

        user_id = request.user_id

        if not user_id in graph:
            logger.error(f"User {user_id} does not exist.")
            return ErrorResponse(message=f"User {user_id} does not exist.")

        if graph[user_id].kind != 'user':
            logger.error(f"User {user_id} is not a user agent.")
            return ErrorResponse(message=f"User {user_id} is not a user agent.")

        del graph[user_id]

        logger.info(f"UserUnregister(id={user_id})")

        return TextResponse(content='ok')

    @app.post('/user/chat')
    async def chat(request: UserChatRequest):
        """
        Handle chat messages from the user.
        """

        user_id = request.user_id

        if not user_id in graph:
            logger.error(f"User {user_id} does not exist.")
            return ErrorResponse(message=f"User {user_id} does not exist.")

        if graph[user_id].kind != 'user':
            logger.error(f"User {user_id} is not a user agent.")
            return ErrorResponse(message=f"User {user_id} is not a user agent.")

        user = graph[request.user_id]

        if request.conversation_id not in user.conversations:
            user.conversations[request.conversation_id] = [
                {'role': 'system', 'content': SYSTEM_PROMPT},
            ]

        messages = user.conversations[request.conversation_id]

        try:
            transport = PythonStdioTransport(
                script_path='/home/yan2u/learn_a2a/net_simulator/mcp/agent_service.py',
                args=['-i', request.user_id, '-r', 'user'],
            )
            messages.append({
                'role': 'user',
                'content': request.message
            })
            messages, choice = await llm.send_message_mcp(
                messages=messages,
                mcp_url=transport
            )
            user.conversations[request.conversation_id] = messages
            return TextResponse(content=str(choice.message.content))
        except Exception as e:
            return ErrorResponse(message=str(e))

    @app.get('/user/messages/{user_id}/{conversation_id}')
    async def get_messages(user_id: str, conversation_id: str) -> ResponseT[List[dict]]:
        """
        Get all messages for a user.
        """

        if not user_id in graph:
            logger.error(f"User {user_id} does not exist.")
            return ErrorResponse(message=f"User {user_id} does not exist.")

        if graph[user_id].kind != 'user':
            logger.error(f"User {user_id} is not a user agent.")
            return ErrorResponse(message=f"User {user_id} is not a user agent.")

        user = graph[user_id]

        if conversation_id not in user.conversations:
            return ErrorResponse(message=f"Conversation {conversation_id} not found for user {user_id}.")

        return ResponseT(
            content=[x.model_dump() if hasattr(x, 'model_dump')
                     else x for x in user.conversations[conversation_id]]
        )

    @app.get('/user/conversations/{user_id}')
    async def get_conversations(user_id: str) -> UserConversationsResponse:
        """
        Get all conversations for a user.
        """

        if not user_id in graph:
            logger.error(f"User {user_id} does not exist.")
            return ErrorResponse(message=f"User {user_id} does not exist.")

        if graph[user_id].kind != 'user':
            logger.error(f"User {user_id} is not a user agent.")
            return ErrorResponse(message=f"User {user_id} is not a user agent.")

        user = graph[user_id]
        convos = list(user.conversations.keys())

        return UserConversationsResponse(
            user_id=user_id,
            conversations=convos
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    uvicorn.run(app, host='0.0.0.0', port=get_config('system.port'))


if __name__ == '__main__':
    main()
