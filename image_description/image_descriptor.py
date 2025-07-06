import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import TaskState, TextPart, Message, FileWithBytes, FilePart
import json

from a2a.client import A2ACardResolver, A2AClient

from a2a.utils import new_agent_text_message

from dotenv import load_dotenv
import os
import base64
from llm_chat import image_response
import asyncio

FAKE_RESPONSE = """This is a fake response for testing purposes.
It only tests the comm framework of a2a."""


async def iter_lines():
    lines = FAKE_RESPONSE.split('\n')
    for line in lines:
        await asyncio.sleep(2)  # Simulate delay for streaming response
        yield line + '\n'


class ImageDescriptorExecutor(AgentExecutor):

    async def execute(self, context: RequestContext, event_queue: EventQueue):
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        if not context.current_task:
            await updater.update_status(TaskState.submitted)

        # parts[0] => image, FileWithBytes
        # parts[1] => text, Extension of image (.jpg, .png, etc.)
        # parts[2] => text, Task Description
        parts = context.message.parts
        if len(parts) < 3:
            print(f"[ImageDescriptor] Invalid parts length: {len(parts)}")
            await updater.update_status(TaskState.failed)
            return

        if isinstance(parts[0].root, FilePart) \
                and isinstance(parts[1].root, TextPart) \
                and isinstance(parts[2].root, TextPart) \
                and isinstance(parts[0].root.file, FileWithBytes):
            img_bytes = parts[0].root.file.bytes
            ext = parts[1].root.text
            prompt = parts[2].root.text
            await updater.update_status(TaskState.working,
                                        new_agent_text_message(
                                            text=f"[ImageDescriptor] Length={len(img_bytes)}, Ext={ext}\n",
                                            context_id=context.context_id,
                                            task_id=context.task_id,
                                        ))
            async for delta in image_response(img_b64=img_bytes, prompt=prompt):
                await updater.update_status(TaskState.working,
                                            new_agent_text_message(text=delta,
                                                                   context_id=context.context_id,
                                                                   task_id=context.task_id,))

        else:
            print(f"[ImageDescriptor] Invalid parts type.")
            await updater.update_status(TaskState.failed)
            return

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        raise Exception('cancel not supported')


class ImageDescriptorAgent:

    def run(self, port: int):
        url = f'http://localhost:{port}'
        skill = AgentSkill(
            id='image_descriptor',
            name='Image Descriptor',
            description='Generates a description of an image based on a prompt.',
            tags=['image', 'description', 'llm'],
            inputModes=['text', 'image'],
            outputModes=['text'],
        )

        card = AgentCard(
            id='image_descriptor',
            name='Image Descriptor',
            description='Generates a description of an image based on a prompt.',
            url=url,
            version='0.1.0',
            defaultInputModes=['text', 'image'],
            defaultOutputModes=['text'],
            capabilities=AgentCapabilities(streaming=True),
            skills=[skill],
            supportsAuthenticatedExtendedCard=False
        )

        request_handler = DefaultRequestHandler(
            agent_executor=ImageDescriptorExecutor(),
            task_store=InMemoryTaskStore()
        )

        server = A2AStarletteApplication(
            agent_card=card,
            http_handler=request_handler,
        )

        uvicorn.run(server.build(), host='0.0.0.0', port=port)


if __name__ == "__main__":
    load_dotenv()
    agent = ImageDescriptorAgent()
    agent.run(port=int(os.getenv('IMAGE_DESCRIPTOR_PORT', 8003)))
