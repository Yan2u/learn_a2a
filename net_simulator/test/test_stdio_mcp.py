
import fastmcp
from fastmcp.client.transports import PythonStdioTransport
import asyncio


async def main():
    transport = PythonStdioTransport(
        script_path="/home/yan2u/learn_a2a/net_simulator/mcp/agent_service.py",
        python_cmd="python3",
        args=['-r', 'user', '-i', '123456']
    )

    async with fastmcp.Client(transport=transport) as mcp:
        tools = await mcp.list_tools()
        print(''.join([x.model_dump_json(indent=2) for x in tools]))

        response = await mcp.call_tool_mcp(name='agent_discover', arguments={})
        print(response.model_dump_json(indent=2))

if __name__ == '__main__':
    asyncio.run(main())
