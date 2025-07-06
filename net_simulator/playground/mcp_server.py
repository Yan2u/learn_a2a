from fastmcp import FastMCP
from pydantic import Field
from typing_extensions import Annotated


def main():
    mcp = FastMCP(name='Test FastMCP Server')

    @mcp.tool()
    def add(
            a: Annotated[float, Field(description="First number to add")],
            b: Annotated[float, Field(description="Second number to add")]
    ) -> float:
        """
        Adds two numbers together.
        """
        return a + b

    @mcp.tool()
    def subtract(
            a: Annotated[float, Field(description="Number to subtract from")],
            b: Annotated[float, Field(description="Number to subtract")]
    ) -> float:
        """
        Subtracts the second number from the first.
        """
        return a - b

    @mcp.tool()
    def multiply(
            a: Annotated[float, Field(description="First number to multiply")],
            b: Annotated[float, Field(description="Second number to multiply")]
    ) -> float:
        """
        Multiplies two numbers together.
        """
        return a * b

    @mcp.tool()
    def returns_a_json() -> dict:
        """
        Returns a JSON object.
        """
        return {"message": "This is a JSON response", "status": "success"}

    mcp.run(transport='sse', host='0.0.0.0', port=8010)


if __name__ == '__main__':
    main()
