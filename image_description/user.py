import uvicorn
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
    FilePart,
    FileWithBytes,
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
import base64
import json


class UserExecutor(AgentExecutor):

    image_descriptor_client: A2AClient
    speech2text_client: A2AClient
    image_descriptor_httpx: httpx.AsyncClient
    speech2text_httpx: httpx.AsyncClient

    def __init__(self):
        super().__init__()

        image_descriptor_url = f"http://localhost:{os.getenv('IMAGE_DESCRIPTOR_PORT', 8003)}"
        speech2text_url = f"http://localhost:{os.getenv('SPEECH2TEXT_PORT', 8004)}"
        self.image_descriptor_httpx = httpx.AsyncClient(
            base_url=image_descriptor_url,
            timeout=360
        )
        image_descriptor_card = asyncio.run(
            A2ACardResolver(httpx_client=self.image_descriptor_httpx, base_url=image_descriptor_url).get_agent_card()
        )
        self.image_descriptor_client = A2AClient(httpx_client=self.image_descriptor_httpx, agent_card=image_descriptor_card)

        self.speech2text_httpx = httpx.AsyncClient(
            base_url=speech2text_url,
            timeout=360
        )
        speech2text_card = asyncio.run(
            A2ACardResolver(httpx_client=self.speech2text_httpx, base_url=speech2text_url).get_agent_card()
        )
        self.speech2text_client = A2AClient(httpx_client=self.speech2text_httpx, agent_card=speech2text_card)

    async def image_desc(self, updater: TaskUpdater, context: RequestContext, prompt: str, img_bytes: str):
        # Text input
        await updater.update_status(TaskState.working,
                                    new_agent_text_message(
                                        text=f"[User] Prompt: {prompt}\n",
                                        context_id=context.context_id,
                                        task_id=context.task_id,
                                    ))
        message_dict = {
            'message': {
                'role': 'user',
                'parts': [
                    {'kind': 'file', 'file': {'bytes': img_bytes}},
                    {'kind': 'text', 'text': 'jpg'},
                    {'kind': 'text', 'text': prompt}
                ],
                'messageId': uuid4().hex,
            }
        }

        message = SendStreamingMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(**message_dict)
        )

        stream = self.image_descriptor_client.send_message_streaming(message)

        async for chunk in stream:
            if chunk.root.result.status.message:
                await updater.update_status(TaskState.working,
                                            new_agent_text_message(
                                                text=chunk.root.result.status.message.parts[0].root.text,
                                                context_id=context.context_id,
                                                task_id=context.task_id,
                                            ))

    async def execute(self, context: RequestContext, event_queue: EventQueue):
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        if not context.current_task:
            await updater.update_status(TaskState.submitted)

        # parts[0] => image/jpeg, FileWithBytes
        # if parts[1] => text, promt directly
        # if parts[1] => audio/wav, FileWithBytes, wav format, use speech2text

        parts = context.message.parts
        if len(parts) < 2:
            await updater.update_status(TaskState.failed)
            return

        if not (isinstance(parts[0].root, FilePart) and isinstance(parts[0].root.file, FileWithBytes)):
            await updater.update_status(TaskState.failed)
            return

        if isinstance(parts[1].root, TextPart):
            await self.image_desc(updater, context, parts[1].root.text, parts[0].root.file.bytes)
            await updater.update_status(TaskState.completed)
        elif isinstance(parts[1].root, FilePart) and isinstance(parts[1].root.file, FileWithBytes):
            # Audio input
            print("[User] Using audio prompt", flush=True)
            wav_bytes = parts[1].root.file.bytes
            await updater.update_status(TaskState.working,
                                        new_agent_text_message(
                                            text=f"[User] Audio Length={len(wav_bytes)}\n",
                                            context_id=context.context_id,
                                            task_id=context.task_id,
                                        ))

            # speec2text
            message_dict = {
                'message': {
                    'role': 'user',
                    'parts': [
                        {'kind': 'file', 'file': {'bytes': wav_bytes}},
                    ],
                    'messageId': uuid4().hex,
                }
            }
            message = SendMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(**message_dict)
            )
            response = await self.speech2text_client.send_message(message)

            for history in response.root.result.history:
                if history.parts[0].root.kind == 'text':
                    await updater.update_status(TaskState.working,
                                                new_agent_text_message(
                                                    text=history.parts[0].root.text,
                                                    context_id=context.context_id,
                                                    task_id=context.task_id,
                                                ))

            transcriptions = response.root.result.status.message.parts[0].root.text

            await self.image_desc(updater, context, transcriptions, parts[0].root.file.bytes)
            await updater.update_status(TaskState.completed)
        else:
            await updater.update_status(TaskState.failed)
            return

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        raise Exception('cancel not supported')


class UserAgent:

    def run(self, port: int):
        url = f'http://localhost:{port}'
        skill = AgentSkill(
            id='image_analyze',
            name='Image Analyze',
            description='Generates a description of an image based on a prompt(in both text and audio form).',
            tags=['image', 'description', 'multimedia', 'llm'],
            inputModes=['text', 'image', 'audio'],
            outputModes=['text'],
        )

        card = AgentCard(
            id='image_analyzer',
            name='Image Analyzer',
            description='Generates a description of an image based on a prompt(in both text and audio form).',
            url=url,
            version='0.1.0',
            defaultInputModes=['text', 'image', 'audio'],
            defaultOutputModes=['text'],
            capabilities=AgentCapabilities(streaming=True),
            skills=[skill],
            supportsAuthenticatedExtendedCard=False
        )

        request_handler = DefaultRequestHandler(
            agent_executor=UserExecutor(),
            task_store=InMemoryTaskStore()
        )

        server = A2AStarletteApplication(
            agent_card=card,
            http_handler=request_handler,
        )

        uvicorn.run(server.build(), host='0.0.0.0', port=port)


if __name__ == "__main__":
    load_dotenv()
    agent = UserAgent()
    agent.run(port=int(os.getenv('USER_PORT', 8005)))
