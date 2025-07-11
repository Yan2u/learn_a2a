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

from pathlib import Path

CWD = Path(__file__).parent

OUTPATIENT_DOCTOR_PROMPT = """You are now an outpatient doctor at a hospital. You are responsible for receiving patients who come to the clinic, communicating and interacting with them, understanding their symptoms, and accurately analyzing their conditions. You then provide a diagnosis and prescription. If necessary, you may need to refer them to a team of specialists for expert diagnosis.

#### Diagnosis

You are connected to the hospital's agent network. In this network, you are the front-line role, directly interacting with patients.

- For patients seeking treatment, if you can determine that their symptoms and conditions are common, you can provide a diagnosis and prescription on your own without seeking assistance from other agents in the network.

- If any of the following situations apply:

- The patient's symptoms involve a specific field or fields;
- You are not confident in providing an accurate diagnosis;
  - The treatment plan is complex and requires detailed specifications for the treatment plan and medication;
- High-risk treatment methods such as surgery are required;

Then you need to submit this situation to the expert meeting host agent (Experts Hosting Agent) in the network. They will receive your request, analyze the situation you are facing, and convene an expert meeting. They will then summarize the opinions of all experts and submit them to you. You must briefly describe your situation and provide information, but do not be overly verbose.

- If the patient's treatment requires medication, you need to contact the Prescription Agent. You will provide your prescription recommendations and receive the prescription from them.

- If the patient's treatment does not require medication, you do not need to contact them.

- Finally, you should provide the patient with a complete diagnosis and prescription (if applicable).

#### Interaction

You should strive for as accurate a diagnosis and analysis of the patient's condition as possible. The patient may not be able to accurately and comprehensively describe their symptoms at the outset, so you need to interact with the user, requesting additional information to assist your analysis. Until you believe you can provide a relatively precise and specific diagnosis, or you believe it is necessary to submit the case to the expert panel for further analysis.

#### Tools

You will use the provided tools to identify agents within the network. You can also use the tools to search for information online to assist your diagnosis. However, when encountering complex conditions, your first choice should be to request assistance from the expert panel, as they have more extensive experience."""


class OutpatientDoctorExecutor(ExecutorBase):
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
            task.id, [{'role': 'system', 'content': OUTPATIENT_DOCTOR_PROMPT}])

        user_input = context.get_user_input(delimiter='\n')
        self.logger.info(f'User input: {user_input}')
        updater = TaskUpdater(event_queue, task.id, task.contextId)

        messages.append({
            'role': 'user',
            'content': user_input
        })

        await updater.start_work(new_agent_text_message(
            text='Starting specialist meeting...',
            context_id=task.contextId,
            task_id=task.id
        ))

        llm = get_llm()
        try:

            messages, choice = await llm.send_message_mcp(messages, transport)
            self.task_messages[task.id] = messages
            self.logger.info(
                f"Task({task.id}) response: {choice.message.content[:100]}...")
            await updater.add_artifact(
                parts=[TextPart(text=choice.message.content)],
                name='spec_meeting_summary'
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


MEDIAL_RECORD_PROMPT = """You are now a staff member responsible for managing patient medical records at a hospital. You are connected to the hospital's agent network. Your information plays a very important role in the diagnostic effectiveness of outpatient agents. Outpatient or specialist agents may request you to retrieve or update the medical records of a specific patient (identified by medical record ID). You need to:

- Retrieve medical records: Using the patient's medical record ID, invoke the tool to retrieve the patient's medical records from the medical record system. You need to provide a brief summary, extract key information, and ensure the efficiency of the diagnosis process.
- Update medical records: Using the patient's medical record ID, update the medical record system. If no ID is provided, it indicates that the patient is a new patient. You will invoke the tool to generate a medical record ID for this patient and save it.

#### Tools

You will use the provided tools to:

- Discover agents in the network.
- Search for information on the internet (if needed).
- Interact with the medical record system: retrieve/update a patient's medical record information.
- Generate medical record IDs.
"""


class MedialRecordExecutor(ExecutorBase):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = context.current_task
        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)
            await self._post_task_start()

        # transport = PythonStdioTransport(
        #     script_path='/home/yan2u/learn_a2a/net_simulator/mcp/agent_service.py',
        #     args=['-i', self.agent_id, '-r', 'agent'],
        # )

        mcp_config = {
            'mcpServers': {
                'agent_network': {
                    'transport': 'stdio',
                    'command': 'python3',
                    'args': ['mcp/agent_service.py', '-i', self.agent_id, '-r', 'agent'],
                    'cwd': str(CWD.parent)
                },
                'medical_record_system': {
                    'transport': 'sse',
                    'url': f"http://localhost:{get_config('mcp.medical_record_port')}/sse",
                }
            }
        }

        messages = self.task_messages.get(
            task.id, [{'role': 'system', 'content': MEDIAL_RECORD_PROMPT}])

        user_input = context.get_user_input(delimiter='\n')
        self.logger.info(f'User input: {user_input}')
        updater = TaskUpdater(event_queue, task.id, task.contextId)

        messages.append({
            'role': 'user',
            'content': user_input
        })

        await updater.start_work(new_agent_text_message(
            text='Starting querying medial record system...',
            context_id=task.contextId,
            task_id=task.id
        ))

        llm = get_llm()
        try:

            messages, choice = await llm.send_message_mcp(messages, mcp_config)
            self.task_messages[task.id] = messages
            self.logger.info(
                f"Task({task.id}) response: {choice.message.content[:100]}...")
            await updater.add_artifact(
                parts=[TextPart(text=choice.message.content)],
                name='medial_record_result'
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


DRUG_INVENTORY_PROMPT = """You are now a hospital staff member responsible for prescribing medications and managing medication inventory. You are connected to the hospital's agent network. You need to process prescription requests from outpatient agents and provide patients with accurate medication lists (including name of the drug and amount, perhaps with medication advice to instruct patients taking the drugs properly) based on the prescription lists issued by outpatient agents. After each prescription is issued, you need to use the tool to update inventory change information.

#### Tools

You will use the provided tools to:

- Discover agents within the network.
- Search online resources to assist you in compiling the medication list.
- Interact with the inventory system to update inventory changes.
"""


class DrugInventoryExecutor(ExecutorBase):

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = context.current_task
        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)
            await self._post_task_start()

        # transport = PythonStdioTransport(
        #     script_path='/home/yan2u/learn_a2a/net_simulator/mcp/agent_service.py',
        #     args=['-i', self.agent_id, '-r', 'agent'],
        # )

        mcp_config = {
            'mcpServers': {
                'agent_network': {
                    'transport': 'stdio',
                    'command': 'python3',
                    'args': ['mcp/agent_service.py', '-i', self.agent_id, '-r', 'agent'],
                    'cwd': str(CWD.parent)
                },
                'inventory_system': {
                    'transport': 'sse',
                    'url': f"http://localhost:{get_config('mcp.drug_inventory_port')}/sse",
                }
            }
        }

        messages = self.task_messages.get(
            task.id, [{'role': 'system', 'content': DRUG_INVENTORY_PROMPT}])

        user_input = context.get_user_input(delimiter='\n')
        self.logger.info(f'User input: {user_input}')
        updater = TaskUpdater(event_queue, task.id, task.contextId)

        messages.append({
            'role': 'user',
            'content': user_input
        })

        await updater.start_work(new_agent_text_message(
            text='Starting querying drug inventory system...',
            context_id=task.contextId,
            task_id=task.id
        ))

        llm = get_llm()
        try:

            messages, choice = await llm.send_message_mcp(messages, mcp_config)
            self.task_messages[task.id] = messages
            self.logger.info(
                f"Task({task.id}) response: {choice.message.content[:100]}...")
            await updater.add_artifact(
                parts=[TextPart(text=choice.message.content)],
                name='drug_inventory_result'
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
