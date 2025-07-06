import json
from abc import ABC, abstractproperty, abstractmethod
import logging
from pathlib import Path
from typing import Any, List, Tuple
from weakref import proxy

import fastmcp
from httpx import get
import httpx
import mcp.types
from openai import AsyncOpenAI, NOT_GIVEN
import openai
from openai.types.chat import ChatCompletionMessageParam
from openai.types.chat.chat_completion import Choice
from uuid import uuid4

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
        self.enable_tools = get_config(f"api_services.{api_service}.tools", True)
        if self.api_key is None:
            raise ValueError(f"API key for {api_service} is not set in the config.")

        proxy_url = get_config(f"proxy.{get_config('proxy.use', 'ssh')}", None)
        if get_config('proxy.enabled', False) and proxy_url:
            self.openai_client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                http_client=httpx.AsyncClient(
                    proxy=proxy_url,
                    transport=httpx.HTTPTransport(local_address='0.0.0.0'),
                    verify=False
                )
            )
        else:
            self.openai_client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )

    @abstractmethod
    async def send_message(self, messages: List[ChatCompletionMessageParam], tools: List[mcp.Tool]) -> List[Choice]:
        pass

    async def send_message_mcp(self, messages: List[ChatCompletionMessageParam], mcp_url: Any) \
            -> Tuple[List[ChatCompletionMessageParam], Choice]:
        if not self.enable_tools:
            raise ValueError("Tools are not enabled for this service.")

        async with fastmcp.Client(transport=mcp_url, timeout=60) as mcp:
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
                        timeout=60
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

    async def send_message(self, messages: List[ChatCompletionMessageParam], tools: List[mcp.Tool]) -> List[Choice]:
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

    async def send_message(self, messages: List[ChatCompletionMessageParam], tools: List[mcp.Tool]) -> List[
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

    async def send_message(self, messages: List[ChatCompletionMessageParam], tools: List[mcp.Tool]) -> List[
            Choice]:
        tools_dict = tool_dict(tools)

        response = await self.openai_client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools_dict,
            reasoning_effort=None
        )

        return response.choices

    async def send_message_mcp(self, messages: List[ChatCompletionMessageParam], mcp_url: str) \
            -> Tuple[List[ChatCompletionMessageParam], Choice]:
        if not self.enable_tools:
            raise ValueError("Tools are not enabled for this service.")

        async with fastmcp.Client(mcp_url, timeout=60) as mcp:
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
                        timeout=60
                    )

                    messages.append(choice.message)

                    messages.append({
                        'role': 'user',
                        'content': tool_response.model_dump_json(),
                        'tool_call_id': call_id
                    })


def get_llm() -> OpenAIService | GeminiOpenAIService | SiliconFlowService:
    api_service = get_config('api_service', OpenAIService.DEFAULT_API_SERVICE)
    if 'gemini' in api_service:
        return GeminiOpenAIService(api_service=api_service)
    elif 'silicon-flow' in api_service:
        return SiliconFlowService(api_service=api_service)
    else:
        return OpenAIService(api_service=api_service)
