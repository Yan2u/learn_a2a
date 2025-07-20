import json
from abc import ABC, abstractproperty, abstractmethod
import logging
from pathlib import Path
from typing import Any, Iterable, List, Tuple, Union
from weakref import proxy

import fastmcp
from httpx import get
import httpx
import mcp.types
from numpy import isin
from openai import AsyncOpenAI, NOT_GIVEN
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionContentPartParam, ChatCompletionContentPartTextParam, ChatCompletionContentPartInputAudioParam, ChatCompletionContentPartImageParam, ChatCompletionMessage, ChatCompletionMessageToolCall
from openai.types.chat.chat_completion import Choice
from uuid import uuid4

from google import genai
from google.genai import types

cwd = Path(__file__).parent
configs = json.load(open(cwd / 'config' / 'config.json', 'r'))


def get_config(key: str, default=None):
    # key can be nested, e.g., 'database.host'
    keys = key.split('.') if '.' in key else [key]

    obj = configs
    for k in keys:
        if k in obj:
            obj = obj[k]
        else:
            return default

    return obj


def save_config(key: str, value):
    global configs

    keys = key.split('.') if '.' in key else [key]
    for k in keys[:-1]:
        if k not in configs:
            configs[k] = {}
        configs = configs[k]

    configs[keys[-1]] = value
    with open(cwd / 'config' / 'config.json', 'w') as f:
        json.dump(configs, f, indent=2)


def tool_dict(tools: List[mcp.types.Tool]) -> List[dict]:
    return [
        {
            'type': "function",
            'function': {
                'name': x.name,
                'description': x.description,
                'parameters': x.inputSchema,
            }
        }
        for x in tools
    ]


class LLMService(ABC):
    DEFAULT_API_SERVICE: str = 'openai'
    openai_client: AsyncOpenAI
    model: str
    api_key: str
    base_url: str
    enable_tools: bool

    def __init__(self, api_service: str = DEFAULT_API_SERVICE):
        self.api_key = get_config(f"api_services.{api_service}.api_key")
        self.model = get_config(f"api_services.{api_service}.model")
        self.base_url = get_config(f"api_services.{api_service}.base_url")
        self.enable_tools = get_config(
            f"api_services.{api_service}.tools", True)
        if self.api_key is None:
            raise ValueError(
                f"API key for {api_service} is not set in the config.")

        proxy_url = get_config(f"proxy.{get_config('proxy.use', 'ssh')}", None)
        if get_config('proxy.enabled', False) and proxy_url:
            self.openai_client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                http_client=httpx.AsyncClient(
                    proxy=proxy_url,
                    transport=httpx.HTTPTransport(local_address='0.0.0.0'),
                    verify=False,
                    timeout=600
                )
            )
        else:
            self.openai_client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=600
            )

    @abstractmethod
    async def send_message(self, messages: List[ChatCompletionMessageParam], tools: List[mcp.Tool] | Any) -> List[Choice]:
        pass

    async def send_message_mcp(self, messages: List[ChatCompletionMessageParam], mcp_url: Any) \
            -> Tuple[List[ChatCompletionMessageParam], Choice]:
        if not self.enable_tools:
            raise ValueError("Tools are not enabled for this service.")

        async with fastmcp.Client(transport=mcp_url, timeout=1800) as mcp:
            tools = await mcp.list_tools()
            while True:
                choices = await self.send_message(
                    messages=messages,
                    tools=tools
                )

                if not choices:
                    raise ValueError("No choices returned from the model.")

                choice = choices[0]
                if choice.finish_reason != 'tool_calls':
                    return messages, choice
                else:
                    tool_name = choice.message.tool_calls[0].function.name
                    tool_args = choice.message.tool_calls[0].function.arguments
                    call_id = choice.message.tool_calls[0].id
                    logger = logging.getLogger('uvicorn')
                    header = f"{'='*20} Tool Call: {tool_name} {'='*20}"
                    logger.info(header)
                    logger.info(f"{'args:':<20}{tool_args}")
                    logger.info(f"{'id:':<20}{call_id}")
                    logger.info('=' * len(header))

                    tool_response = await mcp.call_tool_mcp(
                        name=tool_name,
                        arguments=json.loads(tool_args),
                        timeout=1800
                    )

                    messages.append(choice.message.model_dump())

                    if call_id:
                        messages.append({
                            'role': 'tool',
                            'content': tool_response.model_dump_json(),
                            'tool_call_id': call_id
                        })
                    else:
                        messages.append({
                            'role': 'tool',
                            'content': tool_response.model_dump_json(),
                        })


class SiliconFlowService(LLMService):
    DEFAULT_API_SERVICE: str = 'silicon-flow'

    def __init__(self, api_service: str = DEFAULT_API_SERVICE):
        super().__init__(api_service=api_service)

    async def send_message(self, messages: List[ChatCompletionMessageParam], tools: List[mcp.Tool] | Any) -> List[Choice]:
        if not self.enable_tools and len(tools) > 0:
            raise ValueError("Tools are not enabled for this service.")

        tools_dict = tool_dict(tools) if self.enable_tools else NOT_GIVEN

        response = await self.openai_client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools_dict,
            extra_body={
                'thinking_budget': 1
            }
        )

        # extract json format tool calls
        if response.choices:
            for i, choice in enumerate(response.choices):
                if choice.message.tool_calls:
                    for j, tool_call in enumerate(choice.message.tool_calls):
                        args = tool_call.function.arguments
                        start_idx = args.find('{')
                        end_idx = args.rfind('}')
                        if start_idx != -1 and end_idx != -1:
                            response.choices[i].message.tool_calls[j].function.arguments = args[start_idx:end_idx + 1]

        return response.choices


class OpenAIService(LLMService):
    DEFAULT_API_SERVICE: str = 'openai'

    def __init__(self, api_service: str = DEFAULT_API_SERVICE):
        super().__init__(api_service=api_service)

    async def send_message(self, messages: List[ChatCompletionMessageParam], tools: List[mcp.Tool] | Any) -> List[
            Choice]:
        tools_dict = tool_dict(tools)

        response = await self.openai_client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools_dict,
        )

        return response.choices


class GeminiOpenAIService(OpenAIService):
    DEFAULT_API_SERVICE = 'gemini'

    def __init__(self, api_service: str = DEFAULT_API_SERVICE):
        super().__init__(api_service=api_service)

    async def send_message(self, messages: List[ChatCompletionMessageParam], tools: List[mcp.Tool] | Any) -> List[
            Choice]:
        tools_dict = tool_dict(tools)

        response = await self.openai_client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools_dict,
            # reasoning_effort=None
        )

        return response.choices

    async def send_message_mcp(self, messages: List[ChatCompletionMessageParam], mcp_url: str) \
            -> Tuple[List[ChatCompletionMessageParam], Choice]:
        if not self.enable_tools:
            raise ValueError("Tools are not enabled for this service.")

        async with fastmcp.Client(mcp_url, timeout=1800) as mcp:
            tools = await mcp.list_tools()
            while True:
                choices = await self.send_message(
                    messages=messages,
                    tools=tools
                )

                if not choices:
                    raise ValueError("No choices returned from the model.")

                choice = choices[0]
                if choice.finish_reason != 'tool_calls':
                    return messages, choice
                else:
                    tool_name = choice.message.tool_calls[0].function.name
                    tool_args = choice.message.tool_calls[0].function.arguments
                    call_id = choice.message.tool_calls[0].id
                    logger = logging.getLogger('uvicorn')
                    header = f"{'='*15} Tool Call: {tool_name} {'='*15}"
                    logger.info(header)
                    logger.info(f"{'args:':<20}{tool_args}")
                    logger.info(f"{'id:':<20}{call_id}")
                    logger.info('=' * len(header))

                    tool_response = await mcp.call_tool_mcp(
                        name=tool_name,
                        arguments=json.loads(tool_args),
                        timeout=1800
                    )

                    messages.append(choice.message)

                    messages.append({
                        'role': 'user',
                        'content': tool_response.model_dump_json(),
                        'tool_call_id': call_id
                    })


class DeepSeekService(OpenAIService):
    DEFAULT_API_SERVICE: str = 'deepseek'

    def __init__(self, api_service: str = DEFAULT_API_SERVICE):
        super().__init__(api_service=api_service)

    async def send_message_mcp(self, messages: List[ChatCompletionMessageParam], mcp_url: Any) \
            -> Tuple[List[ChatCompletionMessageParam], Choice]:
        if not self.enable_tools:
            raise ValueError("Tools are not enabled for this service.")

        async with fastmcp.Client(transport=mcp_url, timeout=1800) as mcp:
            tools = await mcp.list_tools()
            while True:
                choices = await self.send_message(
                    messages=messages,
                    tools=tools
                )

                if not choices:
                    raise ValueError("No choices returned from the model.")

                choice = choices[0]
                if choice.finish_reason != 'tool_calls':
                    return messages, choice
                else:
                    tool_name = choice.message.tool_calls[0].function.name
                    tool_args = choice.message.tool_calls[0].function.arguments
                    call_id = choice.message.tool_calls[0].id
                    logger = logging.getLogger('uvicorn')
                    header = f"{'='*20} Tool Call: {tool_name} {'='*20}"
                    logger.info(header)
                    logger.info(f"{'args:':<20}{tool_args}")
                    logger.info(f"{'id:':<20}{call_id}")
                    logger.info('=' * len(header))

                    tool_response = await mcp.call_tool_mcp(
                        name=tool_name,
                        arguments=json.loads(tool_args),
                        timeout=1800
                    )

                    messages.append(choice.message.model_dump())

                    messages.append({
                        'role': 'tool',
                        'content': tool_response.model_dump_json(),
                        'tool_call_id': call_id
                    })

# LLM Gemini Service, But implement using genai api...


class GeminiGenAIService(LLMService):
    DEFAULT_API_SERVICE = 'gemini-genai'
    gemini_client: genai.Client

    def __init__(self, api_service: str = DEFAULT_API_SERVICE):
        self.api_key = get_config(f"api_services.{api_service}.api_key")
        self.model = get_config(f"api_services.{api_service}.model")
        self.base_url = get_config(f"api_services.{api_service}.base_url")
        self.enable_tools = get_config(
            f"api_services.{api_service}.tools", True)

        if self.api_key is None:
            raise ValueError(
                f"API key for {api_service} is not set in the config.")

        proxy_url = get_config(f"proxy.{get_config('proxy.use', 'ssh')}", None)
        if get_config('proxy.enabled', False) and proxy_url:
            self.gemini_client = genai.Client(
                api_key=self.api_key,
                http_options=types.HttpOptions(
                    base_url=self.base_url,
                    async_client_args={'proxy': proxy_url}
                )
            )
        else:
            self.gemini_client = genai.Client(
                api_key=self.api_key,
                http_options=types.HttpOptions(
                    base_url=self.base_url
                )
            )

    def _openai_content_to_genai(self, content: Union[str, Iterable[ChatCompletionContentPartParam]]):
        if isinstance(content, str):
            return [types.Part.from_text(text=content)]
        else:
            result = []
            for item in content:
                if item['type'] == 'text':
                    result.append(types.Part.from_text(text=item['text']))
                elif item['type'] == 'image_url':
                    # the image_url is like data:image/png;base64,xxx
                    # we need to extract the base64 part and mime_type part
                    b64_bytes = item['image_url']['url'].split(',')[1]
                    mime_type = item['image_url']['url'].split(';')[0].split(':')[1]
                    result.append(types.Part.from_bytes(
                        data=b64_bytes,
                        mime_type=mime_type
                    ))
                elif item['type'] == 'input_audio':
                    b64_bytes = item['input_audio']['data']
                    mime_type = f"audio/{item['input_audio']['format']}"
                    result.append(types.Part.from_bytes(
                        data=b64_bytes,
                        mime_type=mime_type
                    ))
                else:
                    raise ValueError(
                        f"Unsupported content part type: {type(item)}")
            return result

    def _openai_message_to_genai(self, messages: List[ChatCompletionMessageParam]) -> Union[types.ContentListUnion, types.ContentListUnionDict]:
        contents = []
        for message in messages:
            if message['role'] == 'user':
                contents.append(types.UserContent(parts=self._openai_content_to_genai(message['content'])))
            elif message['role'] == 'assistant':
                if not message['content']:
                    continue
                contents.append(types.ModelContent(parts=self._openai_content_to_genai(message['content'])))
            elif message['role'] == 'tool':
                contents.append(
                    types.Part.from_function_response(
                        name=message['tool_call_id'],
                        response={'result': message['content']}
                    )
                )
            elif message['role'] == 'system':
                pass
            else:
                raise ValueError(
                    f"Unsupported message role: {message['role']}. Only 'user' and 'assistant' roles are supported.")
        return contents

    async def send_message(self, messages: List[ChatCompletionMessageParam], tools: List[mcp.Tool] | Any) -> List[Choice]:
        # tools as mcp transport
        async with fastmcp.Client(tools) as mcp_server:
            system_prompts = '\n'.join([str(x['content']) for x in messages if x['role'] == 'system'])
            response = await self.gemini_client.aio.models.generate_content(
                model=self.model,
                contents=self._openai_message_to_genai(messages),
                config=types.GenerateContentConfig(
                    system_instruction=system_prompts,
                    tools=[mcp_server.session],
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        disable=True
                    )
                )
            )

            if not response.candidates:
                raise ValueError("No candidates returned from the model.")

            # text response
            candidate = response.candidates[0]

            choice = None
            # function call
            for part in candidate.content.parts:
                if part.function_call:
                    choice = Choice(
                        finish_reason='tool_calls',
                        index=0,
                        message=ChatCompletionMessage(
                            role='assistant',
                            content=None,
                            tool_calls=[
                                ChatCompletionMessageToolCall(
                                    id=part.function_call.name,
                                    function={'name': part.function_call.name, 'arguments': json.dumps(part.function_call.args)},
                                    type='function'
                                )
                            ]
                        )
                    )

                    return [choice]

            text = '\n'.join([str(x.text) for x in candidate.content.parts if x.text is not None])
            choice = Choice(
                finish_reason='stop',
                index=0,
                message=ChatCompletionMessage(
                    content=text,
                    role='assistant'
                )
            )

            return [choice]

    async def send_message_mcp(self, messages: List[ChatCompletionMessageParam], mcp_url: Any) \
            -> Tuple[List[ChatCompletionMessageParam], Choice]:
        if not self.enable_tools:
            raise ValueError("Tools are not enabled for this service.")

        async with fastmcp.Client(transport=mcp_url, timeout=1800) as mcp:
            while True:
                choices = await self.send_message(
                    messages=messages,
                    tools=mcp_url
                )

                if not choices:
                    raise ValueError("No choices returned from the model.")

                choice = choices[0]
                if choice.finish_reason != 'tool_calls':
                    return messages, choice
                else:
                    tool_name = choice.message.tool_calls[0].function.name
                    tool_args = choice.message.tool_calls[0].function.arguments
                    call_id = choice.message.tool_calls[0].id
                    logger = logging.getLogger('uvicorn')
                    header = f"{'='*20} Tool Call: {tool_name} {'='*20}"
                    logger.info(header)
                    logger.info(f"{'args:':<20}{tool_args}")
                    logger.info(f"{'id:':<20}{call_id}")
                    logger.info('=' * len(header))

                    tool_response = await mcp.call_tool_mcp(
                        name=tool_name,
                        arguments=json.loads(tool_args),
                        timeout=1800
                    )

                    messages.append(choice.message.model_dump())

                    if call_id:
                        messages.append({
                            'role': 'tool',
                            'content': tool_response.model_dump_json(),
                            'tool_call_id': call_id
                        })
                    else:
                        messages.append({
                            'role': 'tool',
                            'content': tool_response.model_dump_json(),
                        })


llm_mapping = {
    'openai': OpenAIService,
    'gemini': GeminiOpenAIService,
    'silicon-flow': SiliconFlowService,
    'deepseek': DeepSeekService,
    'gemini-genai': GeminiGenAIService
}


def get_llm() -> OpenAIService | GeminiOpenAIService | SiliconFlowService:
    api_service = get_config('api_service', OpenAIService.DEFAULT_API_SERVICE)
    if api_service in llm_mapping:
        return llm_mapping[api_service](api_service=api_service)
    else:
        return OpenAIService(api_service=api_service)

# file system


def create_file(b64_bytes: str, media_type: str) -> str:
    """
    Create a file in the file system and return its ID.
    """
    file_id = str(uuid4())
    fs_folder = cwd / 'data' / 'filesystem'
    fs_folder.mkdir(parents=True, exist_ok=True)

    fs_index_json = fs_folder / 'index.json'
    if not fs_index_json.exists():
        fs_index_json.write_text('{}')

    file_id = str(uuid4())
    file_path = fs_folder / file_id
    with open(file_path, 'wb') as f:
        f.write(b64_bytes.encode('utf-8'))

    with open(fs_index_json, 'r+', encoding='utf-8') as f:
        index = json.load(f)
        index[file_id] = {
            'media_type': media_type,
        }
        f.seek(0)
        json.dump(index, f, indent=2)

    return file_id


def get_file(file_id: str) -> Tuple[str, str] | None:
    """
    Get a file from the file system by its ID.
    Returns the file's content and media type.
    """
    fs_folder = cwd / 'data' / 'filesystem'
    fs_index_json = fs_folder / 'index.json'

    if not fs_index_json.exists():
        fs_index_json.write_text('{}')

    with open(fs_index_json, 'r', encoding='utf-8') as f:
        index = json.load(f)

    if file_id not in index:
        return None

    file_path = fs_folder / file_id
    if not file_path.exists():
        return None

    with open(file_path, 'rb') as f:
        content = f.read()

    return content.decode('utf-8'), index[file_id]['media_type']


def clear_files() -> None:
    """
    Clear all files in the file system.
    """
    fs_folder = cwd / 'data' / 'filesystem'
    if fs_folder.exists():
        for item in fs_folder.iterdir():
            if item.is_file():
                item.unlink()
        fs_index_json = fs_folder / 'index.json'
        if fs_index_json.exists():
            fs_index_json.unlink()  # Remove the index file
    else:
        # Ensure the folder exists
        fs_folder.mkdir(parents=True, exist_ok=True)
