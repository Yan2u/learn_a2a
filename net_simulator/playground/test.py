from openai.types.chat import ChatCompletionUserMessageParam

x = ChatCompletionUserMessageParam({
    'role': 'user',
    'content': 'What is LLM? Search and return in plain text format.'
})

print(x)
