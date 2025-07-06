from openai import OpenAI

if __name__ == "__main__":
    client = OpenAI(api_key="",
                    base_url="https://api.siliconflow.cn/v1")
    response = client.chat.completions.create(
        # model='Pro/deepseek-ai/DeepSeek-R1',
        model="deepseek-ai/DeepSeek-V3",
        messages=[
            {'role': 'system', 'content': 'you are a helpful assistant.'},
            {'role': 'user',
             'content': "what is LLM?"}
        ],
        stream=False
    )

    print(response.choices[0].message.content)
