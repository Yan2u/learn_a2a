import asyncio
import logging
import time
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Literal, Tuple, TypeVar
from uuid import uuid4

import fastapi
import uvicorn
from a2a.types import (Artifact, Task, TaskArtifactUpdateEvent, TextPart,
                       TaskStatusUpdateEvent, FilePart, FileWithBytes)
from a2a.utils import get_text_parts
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastmcp.client.transports import PythonStdioTransport
from numpy import vsplit
from pydantic import BaseModel

from net_simulator.datamodels import (AgentInteraction, PublicAgentNode,
                                      StampedTask, UserAgentNode)
from net_simulator.msgs import (AgentInteractionAddRequest,
                                AgentKeepAliveRequest, AgentRegistryInfo,
                                AgentRegistryRequest, AgentRegistryResponse,
                                AgentTaskCountAddRequest, ErrorResponse,
                                ResponseT, TextResponse, UserChatRequest,
                                UserConversationsResponse, UserMessageResponse,
                                UserRegisterRequest, AgentInteractionDeleteRequest)
from net_simulator.utils import (OpenAIService, SiliconFlowService, clear_files, create_file, get_config,
                                 get_llm)

CWD = Path(__file__).parent
ROLE = get_config('system.role')
CONFIG_ROOT = CWD.parent / 'config'

SYSTEM_PROMPT = (CONFIG_ROOT / 'user_agent_prompts' /
                 f"{ROLE}.txt").read_text()


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
        clear_files()
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
            category=request.category,
            tasks={},
            expose=request.expose,
            visible_to=request.visible_to
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

    @app.post('/agents/discover')
    def discover_agents(request: AgentKeepAliveRequest) -> ResponseT[List[AgentRegistryInfo]]:
        """
        Discover public agents registered with the manager.
        This is used to find available agents for interaction.
        """

        result = []
        if request.agent_id not in graph:
            logger.error(f"Invalid request with ID {request.agent_id}.")
            return ErrorResponse(
                message=f"Invalid request with ID {request.agent_id}.",
            )
        current_agent = graph[request.agent_id]
        for agent_id, agent in graph.items():
            if agent.kind != 'public':
                continue
            is_visible = agent.expose and (
                (agent.visible_to is None) or current_agent.category in agent.visible_to)
            if is_visible or agent.category == current_agent.category:
                result.append(AgentRegistryInfo(
                    agent_id=agent_id,
                    name=agent.name,
                    url=agent.url,
                ))

        return ResponseT(content=result)

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
                src.interactions.append(AgentInteraction(
                    dst_id=request.dst_id,
                    message=request.message
                ))
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
    def delete_agent_interaction(request: AgentInteractionDeleteRequest):
        """
        Delete an interaction between two agents.
        This is used to build the network graph of agent interactions.
        """

        if request.src_id in graph and request.dst_id in graph:
            src = graph[request.src_id]
            for inter in src.interactions:
                if inter.dst_id == request.dst_id:
                    src.interactions.remove(inter)
                    logger.info(
                        f"Interaction DELETE: {request.src_id} -> {request.dst_id}")
                    break
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

    @app.get('/interactions/user/{user_id}')
    def get_user_interactions(user_id: str) -> ResponseT[List[Tuple[str, str]]]:
        """
        Get interactions for a specific user agent.
        This is used to build the network graph of agent interactions.
        """

        if user_id not in graph:
            logger.error(f"User({user_id}) not found.")
            return ErrorResponse(
                message=f"User({user_id}) not found.",
            )

        if graph[user_id].kind != 'user':
            logger.error(f"User({user_id}) is not a user agent.")
            return ErrorResponse(
                message=f"User({user_id}) is not a user agent.",
            )

        user = graph[user_id]
        return ResponseT(content=[[inter.dst_id, graph[inter.dst_id].name] for inter in user.interactions])

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
        logger.info(
            f"Agent({request.agent_id}) task_count ADD -> {agent.task_count}.")
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
            logger.info(
                f"Agent({request.agent_id}) task_count DELETE -> {agent.task_count}.")
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
    def task_add(user_id: str, request: StampedTask):
        """
        Handle task update requests.
        """

        if not user_id in graph:
            logger.error(f"User {user_id} does not exist.")
            return ErrorResponse(message=f"User {user_id} does not exist.")

        # if graph[user_id].kind != 'user':
        #     logger.error(f"User {user_id} is not a user agent.")
        #     return ErrorResponse(message=f"User {user_id} is not a user agent.")

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

        # if graph[user_id].kind != 'user':
        #     logger.error(f"User {user_id} is not a user agent.")
        #     return ErrorResponse(message=f"User {user_id} is not a user agent.")

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

        # if graph[user_id].kind != 'user':
        #     logger.error(f"User {user_id} is not a user agent.")
        #     return ErrorResponse(message=f"User {user_id} is not a user agent.")

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

    @app.get('/events/get/all_tasks')
    def get_all_tasks() -> ResponseT[Dict[str, Dict[str, Any]]]:
        """
        Retrieve all tasks from all users.
        """

        all_tasks = {}
        for user_id, user in graph.items():
            for task_id, task in user.tasks.items():
                all_tasks[f"{user_id}:{task_id}"] = {
                    'id': task.id,
                    'status': str(task.status.state),
                    'message': task.status.message.model_dump() if task.status.message else None,
                    'timestamp': task.timestamp,
                    'artifacts': [x.name for x in task.artifacts] if task.artifacts is not None else [],
                }

        return ResponseT(content=all_tasks)

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
                    'message': v.status.message.model_dump() if v.status.message else None,
                    'timestamp': v.timestamp,
                    'artifacts': [x.name for x in v.artifacts] if v.artifacts is not None else [],
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

    @app.get('/events/get/all_artifacts')
    def get_all_artifacts() -> ResponseT[List[Artifact]]:
        """
        Retrieve all artifacts from all users.
        """

        all_artifacts = []
        for _, user in graph.items():
            for task in user.tasks.values():
                if task.artifacts:
                    all_artifacts.extend(
                        task.artifacts if task.artifacts else [])

        return ResponseT(content=all_artifacts)

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
            name=request.user_name,
            conversations={},
            tasks={}
        )

        logger.info(
            f"UserRegistered(id={request.user_id}, name={request.user_name})")

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

    @app.post('/user/unregister_all')
    def user_unregister_all():
        """
        Unregister all users from the server.
        """

        user_ids = [x for x in graph.keys() if graph[x].kind == 'user']
        for user_id in user_ids:
            del graph[user_id]
            logger.info(f"UserUnregister(id={user_id})")
        logger.info("All users unregistered.")
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

        user_text = '\n'.join(get_text_parts(request.message))
        user_media = []

        for item in request.message:
            part = item.root
            if isinstance(part, TextPart):
                continue
            if isinstance(part, FilePart):
                if not isinstance(part.file, FileWithBytes):
                    return ErrorResponse(message="Only FileWithBytes is supported.")
                media_type = part.file.mimeType
                if (not media_type) or (media_type not in get_config('system.supported_media_types')):
                    return ErrorResponse(message=f"Unsupported media type: {media_type}")
                if part.file.mimeType.startswith('image/'):
                    user_media.append({
                        'type': 'image_url',
                        'image_url': {
                            'url': f"data:{media_type};base64,{part.file.bytes}",
                        }
                    })
                    file_id = create_file(part.file.bytes, part.file.mimeType)
                    user_media.append({
                        'type': 'text',
                        'text': f"The ID of this image in the file system is {file_id}. You can use this ID to communicating with other agents."
                    })
                    logger.info(
                        f"Image(type={part.file.mimeType}, size={len(part.file.bytes)}, id={file_id}) added to chat message.")
                elif part.file.mimeType.startswith('audio/'):
                    user_media.append({
                        'type': 'input_audio',
                        'input_audio': {
                            'data': part.file.bytes,
                            'format': part.file.mimeType.split('/')[1],
                        }
                    })
                    file_id = create_file(part.file.bytes, part.file.mimeType)
                    user_media.append({
                        'type': 'text',
                        'text': f"The ID of this video in the file system is {file_id}. You can use this ID to communicating with other agents."
                    })
                    logger.info(
                        f"Audeo(type={part.file.mimeType}, size={len(part.file.bytes)}, id={file_id}) added to chat message.")
            else:
                return ErrorResponse(message=f"Unsupported part type: {type(part)}")

        try:
            transport = PythonStdioTransport(
                script_path='/home/yan2u/learn_a2a/net_simulator/mcp/agent_service.py',
                args=['-i', request.user_id, '-r', 'user'],
            )
            if not user_media:
                messages.append({
                    'role': 'user',
                    'content': user_text
                })
            else:
                messages.append({
                    'role': 'user',
                    'content': [
                        {
                            'type': 'text',
                            'text': user_text
                        },
                        *user_media
                    ]
                })
            messages, choice = await llm.send_message_mcp(
                messages=messages,
                mcp_url=transport
            )
            user.conversations[request.conversation_id] = messages
            return TextResponse(content=str(choice.message.content))
        except Exception as e:
            logger.error(f"Error /user/chat: {traceback.format_exc()}")
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
