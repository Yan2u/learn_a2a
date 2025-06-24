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
from llm_chat import speech2text


class Speech2TextExecutor(AgentExecutor):

    async def execute(self, context: RequestContext, event_queue: EventQueue):
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        if not context.current_task:
            await updater.update_status(TaskState.submitted)
        await updater.update_status(TaskState.working)

        # parts[0] => audio, FileWithBytes, wav format
        parts = context.message.parts
        if len(parts) < 1:
            await updater.update_status(TaskState.failed)
            return
        if isinstance(parts[0].root, FilePart) and isinstance(parts[0].root.file, FileWithBytes):
            wav_bytes = parts[0].root.file.bytes
            # save to file
            with open('temp_audio.wav', 'wb') as f:
                f.write(base64.b64decode(wav_bytes))

            await updater.update_status(TaskState.working,
                                        new_agent_text_message(
                                            text=f"[Speech2Text] Length={len(wav_bytes)}\n",
                                            context_id=context.context_id,
                                            task_id=context.task_id,
                                        ))
            transcriptions = await speech2text('temp_audio.wav')
            print(transcriptions)
            await updater.complete(new_agent_text_message(
                text=transcriptions,
                context_id=context.context_id,
                task_id=context.task_id,
            ))
        else:
            await updater.update_status(TaskState.failed)
            return

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        raise Exception('cancel not supported')


class Speech2TextAgent:

    def run(self, port: int):
        url = f'http://localhost:{port}'
        skill = AgentSkill(
            id='speech2text',
            name='Speech to Text',
            description='Converts audio files to text using OpenAI\'s Whisper model.',
            input_types=['audio/wav'],
            output_types=['text/plain'],
            tags=['audio', 'transcription', 'whisper'],
        )

        card = AgentCard(
            id='speech2text',
            name='Speech to Text Agent',
            description='An agent that converts audio files to text using OpenAI\'s Whisper model.',
            url=url,
            version='0.1.0',
            defaultInputModes=['text/plain', 'audio/wav'],
            defaultOutputModes=['text/plain'],
            capabilities=AgentCapabilities(streaming=False),
            skills=[skill],
            supportsAuthenticatedExtendedCard=False
        )

        request_handler = DefaultRequestHandler(
            agent_executor=Speech2TextExecutor(),
            task_store=InMemoryTaskStore()
        )

        server = A2AStarletteApplication(
            agent_card=card,
            http_handler=request_handler,
        )

        uvicorn.run(server.build(), host='0.0.0.0', port=port)


if __name__ == "__main__":
    load_dotenv()
    agent = Speech2TextAgent()
    agent.run(port=int(os.getenv('SPEECH2TEXT_PORT', 8004)))
