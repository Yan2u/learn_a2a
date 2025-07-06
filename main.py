from google import genai
from google.genai import types

client = genai.Client(api_key='')

for chunk in client.models.generate_content_stream(
    model='gemini-2.5-pro',
    contents='What is LLM?'
):
    print(chunk.text, end='', flush=True)

print()
