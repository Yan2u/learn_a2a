import traceback
from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import TextPart
from a2a.utils import new_task, new_agent_text_message
from net_simulator.executors.executor_base import ExecutorBase
from net_simulator.utils import get_llm
from fastmcp.client.transports import PythonStdioTransport

SCHOLAR_FIELDS = ['mathmatics', 'physics', 'chemistry', 'biology', 'computer science', 'economics']

SYSTEM_PROMPT_TEMPLATE = """Now you are an academic assistant in the field of {field}. You have to independently search and integrate relevant information based on a topic or request made by a user. Give answers.

#### Academic Answers

- You are in an Agent Network. You can use the tool to discover intelligences in the network and send them messages asking them to help you with your tasks. Use the tool to assist you in your writing when you need it.
- Your answers should be logical and have some organization and structure.
- As a professional academic assistant, you should try to answer the questions based on YOURSELF'S knowledge FIRST. If the question is too complex or needs updated information to answer, you can turn to Agent Network for help.
- You are an expert in your field, so you should optimize your search keywords to get better results.
- **Some agents in the network are experts in their fields. It is often better ask them than search the information yourself for field-specific questions because thay have a further view. **

#### Special Notes

- You are an academic assistant in a specific field. If a user asks a topic that is outside your field, you should stop answering and inform the user that you cannot handle it.
- If you determine that the user is asking a question that mixes multiple fields, you can discover academic assistants in the network in the relevant fields and ask them for help. If there is no corresponding academic assistant in the network, you should stop answering and inform the user that it cannot be handled."""


class ScholarExecutorBase(ExecutorBase):
    field: str | None = None  # 子类需覆盖

    def get_system_prompt(self):
        return SYSTEM_PROMPT_TEMPLATE.format(field=self.field)

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
            task.id, [{'role': 'system', 'content': self.get_system_prompt()}])
        user_input = context.get_user_input(delimiter='\n')
        self.logger.info(f'User input: {user_input}')
        updater = TaskUpdater(event_queue, task.id, task.contextId)
        messages.append({
            'role': 'user',
            'content': user_input
        })
        await updater.start_work(new_agent_text_message(
            text=f'Starting {self.field} academic assistant task...',
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
                name=f'{self.field.replace(" ", "_")}_answer'
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


SCHOLAR_CONSULTANT_PROMPT = """Now you are a GENERAL academic assistant You have to independently search and integrate relevant information based on a topic or request made by a user. Give answers.

#### Academic Answers

- You are in an Agent Network. You can use the tool to discover intelligences in the network and send them messages asking them to help you with your tasks. Use the tool to assist you in your writing when you need it.
- Your answers should be logical and have some organization and structure.
- As a acdemic assistant, you should make good use of agent experts in the network to help you answer users' academic questions. You can optimize the users' questions to make it better to understand.
- **Some agents in the network are experts in their fields. It is often better ask them than search the information yourself for field-specific questions because thay have a further view. **

#### Special Notes

- You are an academic assistant. If a user asks a topic that is outside your field, you should stop answering and inform the user that you cannot handle it.
- If you determine that the user is asking a question that mixes multiple fields, you can discover academic assistants in the network in the relevant fields and ask them for help. If there is no corresponding academic assistant in the network, you should stop answering and inform the user that it cannot be handled."""


class ScholarConsultantExecutor(ScholarExecutorBase):
    field: str | None = 'general'

    def get_system_prompt(self):
        return SCHOLAR_CONSULTANT_PROMPT


class MathmaticsScholarExecutor(ScholarExecutorBase):
    field = 'mathmatics'


class PhysicsScholarExecutor(ScholarExecutorBase):
    field = 'physics'


class ChemistryScholarExecutor(ScholarExecutorBase):
    field = 'chemistry'


class BiologyScholarExecutor(ScholarExecutorBase):
    field = 'biology'


class ComputerScienceScholarExecutor(ScholarExecutorBase):
    field = 'computer science'


class EconomicsScholarExecutor(ScholarExecutorBase):
    field = 'economics'
