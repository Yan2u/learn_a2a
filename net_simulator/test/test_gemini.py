import fastmcp
from openai import AsyncOpenAI
import asyncio

from net_simulator.utils import OpenAIService, get_llm, tool_dict, GeminiOpenAIService, SiliconFlowService


async def main():
    llm = get_llm()
    # llm = OpenAIService()
    messages, choice = await llm.send_message_mcp(
        messages=[
            {'role': 'system', 'content': 'You are a helpful assistant.'},
            {'role': 'user', 'content': 'What is LLM? You may use tools to answer.'},
        ],
        mcp_url='http://localhost:8081/sse',
    )

    print(choice.model_dump_json(indent=2))


if __name__ == '__main__':
    asyncio.run(main())
