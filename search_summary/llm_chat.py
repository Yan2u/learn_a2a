import os
from openai import AsyncOpenAI
from dotenv import load_dotenv

client = None
load_dotenv()


async def get_llm_response(system_prompt: str, user_prompt: str) -> str:
    """
    调用 OpenAI API 获取模型响应。

    Args:
        system_prompt: 系统提示词，定义模型的角色和行为。
        user_prompt: 用户的输入。

    Returns:
        LLM生成的文本响应。
    """
    global client
    if client is None:
        client = AsyncOpenAI(
            base_url=os.getenv('BASE_URL'),
            api_key=os.getenv('API_KEY')
        )
    try:
        response = await client.chat.completions.create(
            model=os.getenv('MODEL'),  # 或者使用 gpt-3.5-turbo 等其他模型
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        print(f"Error calling API: {e}")
        return f"Error: Failed to get response from LLM. Details: {e}"


async def get_llm_response_stream(system_prompt: str, user_prompt: str):
    global client
    if client is None:
        client = AsyncOpenAI(
            base_url=os.getenv('BASE_URL'),
            api_key=os.getenv('API_KEY')
        )
    try:
        response = await client.chat.completions.create(
            model=os.getenv('MODEL'),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            stream=True,
        )

        async for chunk in response:
            if not chunk.choices:
                continue
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
            if chunk.choices[0].delta.reasoning_content:
                yield chunk.choices[0].delta.reasoning_content
    except Exception as e:
        print(f"Error calling API: {e}")
        yield f"Error: Failed to get response from LLM. Details: {e}"
