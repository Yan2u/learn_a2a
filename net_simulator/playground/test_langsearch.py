import httpx
import asyncio


async def main():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url='https://api.langsearch.com/v1/web-search',
            json={
                'query': 'deepseek-r1 0528',
                'freshness': 'noLimit',
                'summary': True,
                'count': 10
            },
            headers={
                'Authorization': 'Bearer sk-ffd6c6316a334e39b2c357d425f2d0b1'
            }
        )

        if response.status_code != 200:
            print(f"Error: {response.status_code} - {response.text}")
            return

        data = response.json()
        pages = data['data']['webPages']['value']

        fields = ['name', 'url', 'snippet', 'summary', 'datePublished']

        for i, page in enumerate(pages):
            print(f"Page #{i + 1} ============================")
            for field in fields:
                print(f"{field + ':':<15}{page[field] if field in page else 'N/A'}")


if __name__ == '__main__':
    asyncio.run(main())
