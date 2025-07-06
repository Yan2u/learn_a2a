from typing import List

import requests
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from typing_extensions import Annotated
from pydantic import Field
from net_simulator.utils import get_config


def main():
    mcp = FastMCP(name='Langsearch Service')

    @mcp.tool(name='Langsearch')
    def search(
            query: Annotated[str, Field(description='query to search for in the Langsearch database')],
            count: Annotated[
                int, Field(description='number of results to return, must be 1 to 10, default=10', default=10)],
    ) -> List[dict]:
        """
        Search the web for given query using Langsearch. Returns 10 results in JSON format.
        Each result includes:
        1) name, 2) URL, 3) a brief snippet of the webpage, 4) a brief summary of the webpage,
        5) date of publication (maybe N/A if not available).
        """

        api_key = get_config('langsearch_api_key')

        response = requests.post(
            url='https://api.langsearch.com/v1/web-search',
            json={
                'query': query,
                'freshness': 'noLimit',
                'summary': True,
                'count': count
            },
            headers={
                'Authorization': f"Bearer {api_key}"
            }
        )

        if response.status_code != 200:
            raise ToolError(f"Search failed. Status code {response.status_code}: {response.text}")

        return response.json()['data']['webPages']['value']

    port = get_config('mcp.langsearch_port')
    mcp.run(host='0.0.0.0', port=port, transport='sse')


if __name__ == '__main__':
    main()
