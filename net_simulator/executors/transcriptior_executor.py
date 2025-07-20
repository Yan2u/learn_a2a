import json

import fastmcp
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import TextPart, FilePart, FileWithBytes, TaskStatusUpdateEvent, TaskState
from a2a.utils import new_task, new_agent_text_message
import httpx

from net_simulator.executors.executor_base import ExecutorBase, GeneralTextExecutor
from net_simulator.utils import OpenAIService, SiliconFlowService, get_config, get_llm

from fastmcp.client.transports import PythonStdioTransport

import traceback

SYSTEM_PROMPT = """You are a professional audio transcription expert. You can help others transcribe audio files into text, and provide professional insights and answers related to audio transcription.

If you can recoginize the language of the audio, you can transcribe it into text using the language in the audio. If you cannot recognize the audio or you do not think it is a speech, you can replay that this is not a speech or the language is not supported.

#### IMAGES, AUDIOS AND FILES

- As a agent in the network, you may communicate with other agents using files (such as images).
- To avoid outputing bytes directly, each time you want to send a file (an image) to other agent, you are supposed to use its **ID in the file system**. And you should pass this ID to him as well. For details, you can read instructions of the tool `agent_send_message`.
"""


class TranscriptorExecutor(GeneralTextExecutor):
    system_prompt = SYSTEM_PROMPT
    name = "transcriptor"
