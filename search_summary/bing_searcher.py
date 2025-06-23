# learn_a2a/search_summary/utils/bing_searcher.py
import requests
from bs4 import BeautifulSoup
import json
from typing import List, Dict, Any
import asyncio


async def get_response(url: str, headers: Dict[str, str]) -> requests.Response:
    """
    异步获取指定 URL 的响应。

    Args:
        url: 请求的 URL。
        headers: 请求头信息。

    Returns:
        requests.Response 对象。
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, requests.get, url, headers)


async def search(query: str, num_results: int = 20) -> List[Dict[str, Any]]:
    """
    使用 Bing 搜索引擎搜索并返回结果。

    Args:
        query: 搜索关键词。
        num_results: 需要返回的最大结果数量。

    Returns:
        一个包含搜索结果的列表，每个结果是一个字典。
    """
    search_url = f"https://www.bing.com/search?q={query}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        response = await get_response(search_url, headers)
        # response = requests.get(search_url, headers=headers)
        response.raise_for_status()  # 如果请求失败则抛出异常

        soup = BeautifulSoup(response.text, "html.parser")

        results = []
        # Bing 的搜索结果通常在 class="b_algo" 的 <li> 元素中
        for item in soup.find_all("li", class_="b_algo", limit=num_results):
            title_tag = item.find("h2")
            link_tag = title_tag.find("a") if title_tag else None
            title = title_tag.text if title_tag else "No Title"
            url = link_tag["href"] if link_tag and "href" in link_tag.attrs else "No URL"

            # 描述通常在 class="b_caption" 的 <div> 中的 <p> 标签里
            desc_container = item.find("div", class_="b_caption")
            description = desc_container.find("p").text if desc_container and desc_container.find("p") else "No Description"

            if url != "No URL":
                results.append({
                    "title": title,
                    "description": description,
                    "url": url,
                })

        return results

    except requests.RequestException as e:
        print(f"Error during Bing search request: {e}")
        return []
