import asyncio
import json

from fastmcp import Client
from net_simulator.utils import get_config, tool_dict, SiliconFlowService, OpenAIService
from openai import OpenAI, AsyncOpenAI

import base64
from pathlib import Path

CWD = Path(__file__).parent


async def main():
    async with Client(f"http://localhost:{get_config('mcp.langsearch_port')}/sse") as client:
        tools = await client.list_tools()

        llm = OpenAIService()
        print(f"API Key: {llm.api_key}")
        print(f"Model: {llm.model}")
        print(f"Base URL: {llm.base_url}")
        img_b64 = base64.b64encode(open(str(CWD / 's1mple.jpg'), 'rb').read()).decode('utf-8')

        messages = [
            {'role': 'system', 'content': 'You are a helpful assistant.'},
            {'role': 'user',
             'content': [
                 {'type': 'text',
                  'text': 'Who is the esports player in this picture? can you search and introduce him briefly? you may use tools provided to search.'},
                 {'type': 'image_url', 'image_url': {
                     'url': f"data:image/jpeg;base64,{img_b64}",
                     'detail': 'low'
                 }}
             ]},
        ]

        choices = await llm.send_message(
            messages=messages,
            tools=tools
        )

        if not choices:
            print("No choice available")
            return
        result = choices[0]
        while result.finish_reason == 'tool_calls':
            tool_name = result.message.tool_calls[0].function.name
            tool_args = result.message.tool_calls[0].function.arguments
            call_id = result.message.tool_calls[0].id
            head_msg = f"{'Tool call:' + tool_name:<30}=================="
            print(head_msg)
            print(f"{'llm:':<15}{result.message.content}")
            print(f"{'name:':<15}{tool_name}")
            print(f"{'args:':<15}{tool_args}")
            print(f"{'id:':<15}{call_id}")
            print('=' * len(head_msg))
            tool_response = await client.call_tool_mcp(name=tool_name, arguments=json.loads(tool_args), timeout=60)
            messages.append(result.message.model_dump())
            messages.append({
                'role': 'tool',
                'content': tool_response.model_dump_json(),
                'tool_call_id': call_id
            })

            choices = await llm.send_message(
                messages=messages,
                tools=tools
            )
            if not choices:
                print("No choice available")
                return
            result = choices[0]

        result = choices[0]
        head_msg = f"{'Final Response:':<30}=================="
        print(head_msg)
        print(result.message.content)
        print('=' * len(head_msg))


if __name__ == "__main__":
    asyncio.run(main())
