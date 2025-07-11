import json

import fastmcp
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import TextPart, FilePart, FileWithBytes, TaskStatusUpdateEvent, TaskState
from a2a.utils import new_task, new_agent_text_message
import httpx

from net_simulator.executors.executor_base import ExecutorBase
from net_simulator.utils import OpenAIService, SiliconFlowService, get_config, get_llm

import traceback

SYSTEM_PROMPT = """Now you are a search and summary assistant. You need to use the tools provided to search the web based on the text or images provided by users. Once the search is completed, you need to return the results in a structured data format according to the format specified by the user (which includes json, xml, csv, markdown, and plain text).

If you think the input provided by the user is not enough to complete the task of searching and summarizing, you also need to return your requirements in the format of structured data, and ask the user to provide more input. I will explain this in detail below.

- Regardless of which format you choose, your answer should include two parts: a list of all search results and a brief summary of the search results.

- After calling the tool to search, you will get: the title, a "snippet" of text taken from the webpage, the URL, a brief summary, and the date (the date may not be available in some cases);
- **List all search results** requires you to organize each search result into a formatted string according to the given data format;
- For a **brief summary**, you can either generate it yourself or directly adopt some summary texts from search results. You also need to organize them into a formatted string.

- For each format, you can freely choose the field names, for example, for JSON, you can return the following structure.

{
    "search_results": [
        {
            "title": "<title of result>",
            "url" : "<url of this result>",
            "summary" : "<summary of this result>",
            "date" : "<date of this result, if exists>"
        }
    ],
    "summary" : "<your summary>"
}

I'm just providing an example. When you actually process the data, you don't have to follow the format I've given, but your format must meet the requirements we've just discussed. This is a description of JSON format data, and it also applies to XML, CSV, Markdown, and plain text format data.

**Your final answer should be a structured JSON string, please answer in this format.**

{
    "status" : "ok",
    "result" : "<your result here>"
}

Among them.

- status field: It can only be "ok", "needs_input", or "error". "ok" indicates that the reply is complete, and "needs_input" indicates that the user's prompt is not sufficient (for example, they didn't specify what to search for, or they didn't specify what format to return), and "error" represents that you are not able to deal with this problem, and you should give a brief reason about that. 
- result field: Convert your structured search and summary results into a string, and fill this field.

**IMPORTANT NOTE**: You are not directly taking to user. **So whatever format the user has required, you must generate you answer in this status-result JSON format**. Your actual response should be in 'result' field (to show a JSON, xml, csv, etc. format required by user). 

**EXAMPLES**

1. User: Can you search about LLM in the web and summarize it in JSON format?

   You should return:

   {
   	"status" : "ok",
   	"result" : "<your result here>"
   }

2. User: i want to summarize in XML format.

   You should return:

   {
       "status" : "needs_input",
       "result" : "..."
   }

3. User: *provided an image*, can you search about what is in the image can answer me in plain text format?

   If you can, you should return:

   {
        "status" : "ok",
        "result" : "<plain text of result here>"
   }
   

   If you cannot identify the picture, just return:

   {
       "status" : "error",
       "result" : "<your problems>"
   }

**DO NOT add any annotations such as ```json outside this JSON string, but just leave it raw.**
"""


class SearchSummaryExecutor(ExecutorBase):

    def _extract_response(self, resp: str) -> str:
        if '```' in resp:
            start_idx = resp.find('{')
            end_idx = resp.rfind('}')
            if start_idx != -1 and end_idx != -1:
                return resp[start_idx:end_idx + 1]
            else:
                self.logger.warning("No valid JSON found in the response.")
                return resp
        else:
            return resp

    async def execute(
            self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        task = context.current_task
        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)
            await self._post_task_start()

        messages = self.task_messages.get(
            task.id, [{'role': 'system', 'content': SYSTEM_PROMPT}])

        user_input = context.get_user_input(delimiter='\n')
        self.logger.info(f'User input: {user_input}')
        updater = TaskUpdater(event_queue, task.id, task.contextId)

        user_image = None
        for part in context.message.parts:
            if isinstance(part.root, FilePart) and isinstance(part.root.file, FileWithBytes):
                user_image = part.root.file.bytes
                break

        if user_image:
            messages.append({
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': user_input},
                    {'type': 'image_url', 'image_url': {
                        'url': f"data:image/jpeg;base64,{user_image}",
                        'detail': 'low'
                    }}
                ]
            })
        else:
            messages.append({
                'role': 'user',
                'content': user_input
            })

        await updater.start_work(new_agent_text_message(
            text='Starting search and summary task...',
            context_id=task.contextId,
            task_id=task.id
        ))

        llm = get_llm()
        try:
            messages, choice = await llm.send_message_mcp(messages,
                                                          f"http://localhost:{get_config('mcp.langsearch_port')}/sse")
            self.task_messages[task.id] = messages
            choice.message.content = self._extract_response(
                choice.message.content)
            self.logger.info(
                f"Task({task.id}) response: {choice.message.content[:100]}...")
            result = json.loads(choice.message.content)
            if result['status'] == 'ok':
                self.logger.info(f"Task({task.id}) ok")
                await updater.add_artifact(
                    name='result',
                    parts=[TextPart(text=str(result['result']))]
                )
                await updater.complete()
            elif result['status'] == 'needs_input':
                self.logger.info(f"Task({task.id}) needs_input")
                await updater.update_status(
                    TaskState.input_required,
                    new_agent_text_message(
                        text=str(result['result']),
                        context_id=task.contextId,
                        task_id=task.id
                    )
                )
            elif result['status'] == 'error':
                self.logger.warning(f"Task({task.id}) error")
                await updater.failed(
                    new_agent_text_message(
                        text=str(result['result']),
                        context_id=task.contextId,
                        task_id=task.id
                    )
                )
            else:
                self.logger.warning(
                    f"Task({task.id}) unknown result type {result['status']}")
                await updater.failed(
                    new_agent_text_message(
                        text='Invalid response from the model. Please try again later.',
                        context_id=task.contextId,
                        task_id=task.id
                    )
                )
        except Exception as e:
            self.logger.error(f"Task({task.id}) error:")
            self.logger.error(traceback.format_exc())
            await updater.failed(
                new_agent_text_message(
                    text=f"Unexpected Error: {e}",
                    task_id=task.id,
                    context_id=task.contextId,
                )
            )

        await self._post_task_end()

    async def cancel(
            self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        raise NotImplementedError()
