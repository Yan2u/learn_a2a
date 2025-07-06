import fastmcp
import asyncio


async def main():
    async with fastmcp.Client('http://localhost:8010/sse') as client:
        tools = await client.list_tools()
        for tool in tools:
            print(tool.model_dump_json(indent=2))

        result = await client.call_tool_mcp(
            name='add',
            arguments={
                'a': 1,
                'b': 2
            },
            timeout=360
        )

        if result.isError:
            print(f"Error: {result.content}")
        else:
            print(result.content)

        result = await client.call_tool_mcp(
            name='returns_a_json',
            arguments={},
            timeout=360
        )

        if result.isError:
            print(f"Error: {result.content}")
        else:
            print(result.content)


if __name__ == '__main__':
    asyncio.run(main())
