from openai import AsyncOpenAI
from openai.types.responses import ResponseTextDeltaEvent
import asyncio
import base64
import json
from dotenv import load_dotenv
import os


async def image_response(img_b64: str, prompt: str):
    load_dotenv()
    openai = AsyncOpenAI(
        api_key=os.getenv('API_KEY'),
    )

    stream = await openai.responses.create(
        model='gpt-4o',
        input=[
            {
                'role': 'system',
                'content': 'You are a helpful assistant.'
            },
            {
                'role': 'user',
                'content': [
                    {
                        'type': 'input_text',
                        'text': prompt
                    },
                    {
                        'type': 'input_image',
                        'image_url': f'data:image/jpeg;base64,{img_b64}'
                    }
                ]
            }
        ],
        stream=True
    )

    async for event in stream:
        if isinstance(event, ResponseTextDeltaEvent):
            yield event.delta


async def speech2text(wav_file_path: str):
    load_dotenv()
    openai = AsyncOpenAI(
        api_key=os.getenv('API_KEY')
    )

    wav_file = open(wav_file_path, 'rb')

    transcriptions = await openai.audio.transcriptions.create(
        model='gpt-4o-transcribe',
        file=wav_file,

    )

    return transcriptions.text
