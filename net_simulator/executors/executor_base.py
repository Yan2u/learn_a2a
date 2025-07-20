import logging
from typing import Dict, List

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_task, new_agent_text_message
from a2a.server.tasks import TaskUpdater
from a2a.types import TextPart, FileWithBytes, FilePart
from fastmcp.client.transports import PythonStdioTransport
import httpx
import traceback
from numpy import isin
from openai.types.chat import ChatCompletionMessageParam

from net_simulator.utils import get_config, get_file, get_llm


class ExecutorBase(AgentExecutor):
    logger: logging.Logger
    task_messages: Dict[str, List[ChatCompletionMessageParam]]
    agent_id: str

    async def _post_task_start(self):
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"http://localhost:{get_config('system.port')}/task_count/add",
                    json={'agent_id': self.agent_id}
                )
        except Exception:
            pass

    async def _post_task_end(self):
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"http://localhost:{get_config('system.port')}/task_count/delete",
                    json={'agent_id': self.agent_id}
                )
        except Exception:
            pass

    def _replace_file_part(self, part: FilePart) -> FilePart:
        """
        Replace the FilePart with a new FilePart that contains the file bytes.
        This is used to ensure that the file bytes are available in the task messages.
        """
        file_bytes, mime_type = get_file(part.file.bytes)
        if file_bytes is None:
            raise ValueError(
                f"File {part.file.name} not found in the file system.")
        self.logger.info(
            f"File(id={part.file.bytes}, type={mime_type}, size={len(file_bytes)})")
        part.file.bytes = file_bytes
        part.file.mimeType = mime_type
        return part

    def __init__(self, agent_id: str):
        self.logger = logging.getLogger('uvicorn')
        self.task_messages = {}
        self.agent_id = agent_id


class GeneralTextExecutor(ExecutorBase):
    """
    General executor for agents. It can handle text, image/jpeg, image/png messages and provide text responses.
    """

    system_prompt: str
    name: str
    mcp_configs: dict | None = None

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = context.current_task
        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)
            await self._post_task_start()

        transport = self.mcp_configs

        if not transport:
            transport = PythonStdioTransport(
                script_path='/home/yan2u/learn_a2a/net_simulator/mcp/agent_service.py',
                args=['-i', self.agent_id, '-r', 'agent'],
            )

        messages = self.task_messages.get(
            task.id, [{'role': 'system', 'content': self.system_prompt}])

        user_input = context.get_user_input(delimiter='\n')
        user_media = []
        for item in context.message.parts:
            part = item.root
            if isinstance(part, FilePart) and isinstance(part.file, FileWithBytes):
                file_id = part.file.bytes
                new_part = self._replace_file_part(part)
                file_obj = new_part.file
                if file_obj.mimeType is None:
                    raise ValueError(
                        f"File {file_obj.name} not specified with mimeType.")
                if not file_obj.mimeType in get_config('system.supported_media_types'):
                    raise ValueError(
                        f"File {file_obj.name} with mimeType {file_obj.mimeType} is not supported.")
                if file_obj.mimeType.startswith('image/'):
                    user_media.append({
                        'type': 'image_url',
                        'image_url': {
                            'url': f"data:image/{file_obj.mimeType.split('/')[1]};base64,{file_obj.bytes}",
                        }
                    })
                elif file_obj.mimeType.startswith('audio/'):
                    user_media.append({
                        'type': 'input_audio',
                        'input_audio': {
                            'data': file_obj.bytes,
                            'format': file_obj.mimeType.replace('audio/', '')
                        }
                    })
                user_media.append({
                    'type': 'text',
                    'text': f"The ID of this file in the file system is {file_id}. You can use this ID to communicate with other agents."
                })

        self.logger.info(f'User input: {user_input}')
        self.logger.info(f'User media: {len(user_media)}')
        updater = TaskUpdater(event_queue, task.id, task.contextId)

        if user_media:
            messages.append({
                'role': 'user',
                'content': [
                    {
                        'type': 'text',
                        'text': user_input
                    },
                    *user_media
                ]
            })
        else:
            messages.append({
                'role': 'user',
                'content': user_input
            })

        await updater.start_work(new_agent_text_message(
            text=f"Agent {self.name} start wjorking...",
            context_id=task.contextId,
            task_id=task.id
        ))

        llm = get_llm()
        try:

            messages, choice = await llm.send_message_mcp(messages, transport)
            self.task_messages[task.id] = messages
            self.logger.info(
                f"Task({task.id}) response: {choice.message.content[:100]}...")
            await updater.add_artifact(
                parts=[TextPart(text=choice.message.content)],
                name=f"{self.name} response",
            )
            await updater.complete()
            await self._post_task_end()
        except Exception as e:
            self.logger.error(f"Task({task.id}) error:")
            self.logger.error(traceback.format_exc())
            await updater.failed(
                new_agent_text_message(
                    text=f"Unexpected Error: {e}",
                    task_id=task.id,
                    context_id=task.contextId,
                )
            )
            await self._post_task_end()
            return

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError()
