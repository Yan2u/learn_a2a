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

from fastmcp.client.transports import PythonStdioTransport

import traceback


SYSTEM_PROMPT = """Now you are an academic essay writing assistant. You have to independently search and integrate relevant information according to the topic or requirement given by the user and write an academic article that is logical and conforms to a standardized structure.

#### Paper Writing

You are in an Agent Network. You can use the tool to discover the agents in the network and send them messages asking them to help you with your tasks. Use the tools to assist you in your writing when you need it.

**Some agents in the network are experts in their fields. It is often better ask them than search the information yourself for field-specific questions because thay have a further view. **

#### Article Structure

You will follow this structure to write your academic article

- Section 1: Abstract. Briefly discuss the purpose and background of your writing; the significance and value of your research project. Also, give some keywords to describe your article.
- Section 2: Body. There is no set format for this section. To ensure that your essay is logical and well reasoned, you may need to subdivide this section into multiple subsections for your writing.
- Section 3: Summary and Future Outlook. Make a general statement about the process and results of your research. Also briefly state again the significance of your research. Then, give some of your views and outlook for the future regarding your research topic.
- Section 4: References. Considering that you may utilize tools to search for information, you may put the links to the information you have searched for here.

#### IMPORTANT NOTICE

- If the topic provided by the user is vague and not easy to start researching, you can stop the task and ask the user to provide more specific and precise instructions.
- Depending on the user's instructions, the length of your article may vary. However, your article should be a minimum of 3000 words. Of these, the abstract section needs to be in condensed language, no less than 50 words, but not more than 200 words. The summary and future outlook section should be no less than 200 words.
"""


class EssayWriterExecutor(ExecutorBase):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = context.current_task
        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)
            await self._post_task_start()

        transport = PythonStdioTransport(
            script_path='/home/yan2u/learn_a2a/net_simulator/mcp/agent_service.py',
            args=['-i', self.agent_id, '-r', 'agent'],
        )

        messages = self.task_messages.get(
            task.id, [{'role': 'system', 'content': SYSTEM_PROMPT}])

        user_input = context.get_user_input(delimiter='\n')
        self.logger.info(f'User input: {user_input}')
        updater = TaskUpdater(event_queue, task.id, task.contextId)

        messages.append({
            'role': 'user',
            'content': user_input
        })

        await updater.start_work(new_agent_text_message(
            text='Starting academic essay writing task...',
            context_id=task.contextId,
            task_id=task.id
        ))

        llm = get_llm()
        try:

            messages, choice = await llm.send_message_mcp(messages, transport)
            self.task_messages[task.id] = messages
            self.logger.info(f"Task({task.id}) response: {choice.message.content[:100]}...")
            await updater.add_artifact(
                parts=[TextPart(text=choice.message.content)],
                name='essay'
            )
            await updater.complete()
            await self._post_task_end()
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
            return

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError()
