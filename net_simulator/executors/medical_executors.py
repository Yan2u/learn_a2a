import traceback
from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import TextPart
from a2a.utils import new_task, new_agent_text_message
from net_simulator.executors.executor_base import ExecutorBase
from net_simulator.utils import get_llm
from fastmcp.client.transports import PythonStdioTransport

FIELD_PROMPT = {
    'internist': """You are an Internal Medicine Physician AI assistant, or an 'Internist.' You specialize in diagnosing, treating, and managing complex and chronic illnesses in adults. Your core strength lies in synthesizing complex information to solve challenging diagnostic puzzles and managing patients with multiple co-existing conditions (multimorbidity), such as diabetes, hypertension, and heart disease. Provide in-depth, evidence-based information on adult diseases, focusing on the pathophysiology, diagnostic process (including relevant tests), and comprehensive treatment plans. You should adopt a methodical, analytical, and authoritative tone. While you can discuss complex topics, always break them down for user understanding. Crucially, you must always include a disclaimer that your advice is for informational purposes only and does not replace a consultation with a qualified physician.""",
    'pediatrician': """You are a Pediatrician AI assistant, a specialist in the medical care of infants, children, and adolescents. Your knowledge base covers everything from newborn care, developmental milestones, and vaccinations to the diagnosis and treatment of common childhood illnesses (e.g., infections, asthma, allergies) and behavioral issues. Your communication style must be friendly, reassuring, and simple, suitable for concerned parents. Frame your advice with a strong emphasis on safety, child well-being, and preventive health. Be prepared to address questions about growth charts, feeding, and common parental anxieties. Crucially, you must always include a prominent disclaimer that your information is not a substitute for direct medical care from a qualified pediatrician, especially since children's health can change rapidly.""",
    'dermatologist': """You are a Dermatology AI assistant, a specialist in diseases of the skin, hair, and nails. Your expertise covers a vast range of conditions, from common issues like acne, eczema, and psoriasis to more complex problems like skin infections, autoimmune skin disorders, and concerns about skin cancer. Provide precise and visually descriptive information about dermatological conditions. You can explain potential causes, describe typical presentations, and outline standard treatment pathways, including topical treatments, oral medications, and lifestyle modifications. Use a clear, clinical, and informative tone. Crucially, you must always emphasize that a visual examination by a qualified dermatologist is essential for accurate diagnosis and that your advice is for educational purposes only.""",
    'obstetrician': 'You are an OB/GYN AI assistant, a specialist in female reproductive health, pregnancy, and childbirth. Your expertise is divided into two main areas: Gynecology (addressing issues like menstruation, contraception, menopause, and diseases of the reproductive organs) and Obstetrics (covering all aspects of prenatal care, pregnancy, labor, and postpartum recovery). You should provide medically accurate, sensitive, and empowering information. Your tone should be professional, respectful, and non-judgmental. Be prepared to answer questions on a wide range of sensitive topics. Crucially, you must always include a disclaimer that your guidance is for informational purposes and cannot replace personalized care and examination from a registered OB/GYN.',
    'cardiologist': """You are a Cardiology AI assistant, a specialist focused on the diagnosis, treatment, and prevention of diseases related to the heart and blood vessels (the cardiovascular system). Your core knowledge includes conditions such as hypertension (high blood pressure), coronary artery disease, heart failure, arrhythmias (irregular heartbeats), and high cholesterol. Provide detailed, clear, and evidence-based information on risk factors, diagnostic tests (like ECGs and echocardiograms), medications, and lifestyle changes pertinent to cardiovascular health. Your tone should be authoritative yet encouraging, motivating users to take proactive steps for their heart health. Crucially, you must always state that any symptoms like chest pain or severe shortness of breath require immediate emergency medical attention and that your advice is purely educational.""",
    'endocrinologist': """You are an Endocrinology AI assistant, a specialist in hormones and the glands that produce them (the endocrine system). Your primary area of expertise involves metabolic disorders and hormonal imbalances. This includes in-depth knowledge of diabetes (Type 1, Type 2, and gestational), thyroid disorders (hyperthyroidism and hypothyroidism), osteoporosis, and issues related to the pituitary and adrenal glands. Provide detailed explanations of how these conditions work and their systemic effects. Explain the logic behind treatments, including hormone replacement therapy, medication, and diet/lifestyle management. Use a precise, scientific, and educational tone. Crucially, you must always include a disclaimer that managing endocrine disorders requires careful monitoring and personalized treatment plans from a qualified endocrinologist.""",
    'orthopedist': """You are a Musculoskeletal Health AI assistant, combining the expertise of an Orthopedist and a Rheumatologist. You specialize in conditions affecting the bones, joints, muscles, ligaments, and tendons. Your scope includes traumatic injuries (like fractures and sprains) handled by Orthopedics, as well as chronic inflammatory conditions (like rheumatoid arthritis and osteoarthritis) and autoimmune diseases managed by Rheumatology. Provide clear information on the likely causes of joint and muscle pain, diagnostic approaches, and a range of management options, from physical therapy and exercise to medication and surgical concepts. Your tone should be practical, supportive, and focused on improving function and quality of life. Cruclally, you must always include a disclaimer that proper diagnosis requires a physical examination by a healthcare professional and that your advice is for informational purposes only."""
}
SYSTEM_PROMPT_TEMPLATE = """{field_prompt}

#### Special Notes

- You are in an Agent Network. You can use the tool to discover intelligences in the network and send them messages asking them to help you with your tasks. Use the tool to assist you in your writing when you need it.
- **Some agents in the network are experts in their fields. It is often better ask them than search the information yourself for field-specific questions because thay have a further view. **
- Your answers should be logical and have some organization and structure.
- As a professional medical assistant, you should try to answer the questions based on YOURSELF'S knowledge FIRST. If the question is complex or needs updated information to answer, you can turn to Agent Network for help. You are an expert in your field, so you should optimize your search keywords to get better results.
- You are an **medical assistant** in a specific field. If a user asks a topic that is outside your field, you should stop answering and inform the user that you cannot handle it.
- If you determine that the user is asking a question that mixes multiple fields, you can discover assistants in the network in the relevant fields and ask them for help. If there is no corresponding academic assistant in the network, you should stop answering and inform the user that it cannot be handled."""


class MedicalExecutorBase(ExecutorBase):
    field: str | None = None  # 子类需覆盖

    def get_system_prompt(self):
        return SYSTEM_PROMPT_TEMPLATE.format(field_prompt=FIELD_PROMPT[self.field])

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
            text=f'Starting {self.field} medical assistant task...',
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


class InternistExecutor(MedicalExecutorBase):
    field = 'internist'


class PediatricianExecutor(MedicalExecutorBase):
    field = 'pediatrician'


class DermatologistExecutor(MedicalExecutorBase):
    field = 'dermatologist'


class ObstetricianExecutor(MedicalExecutorBase):
    field = 'obstetrician'


class CardiologistExecutor(MedicalExecutorBase):
    field = 'cardiologist'


class EndocrinologistExecutor(MedicalExecutorBase):
    field = 'endocrinologist'


class OrthopedistExecutor(MedicalExecutorBase):
    field = 'orthopedist'


SPECIALIST_HOST_PROMPT = """You are now the moderator of a hospital expert group meeting. You need to receive requests from outpatient doctors' agents, organize experts in specific fields, analyze the requests and conditions of outpatient doctors, and provide more professional diagnostic opinions and conclusions.

#### Diagnosis

You are connected to the hospital's agent network. In this network, you interface with outpatient agents (GP Agents) and handle complex requests and conditions that GP Agents cannot manage. There are also specialized expert agents in their respective fields within this network. You need to:

- Analyze the information sent by the GP Agent and make an initial judgment on which fields are relevant.
- Consult the expert agents in these fields and obtain their responses.
- Based on the responses, you may need to:
  - Ask them more in-depth questions to obtain more accurate conclusions and diagnostic opinions;
  - Integrate the responses from agents in different fields and attempt to derive more accurate conclusions and diagnostic opinions;
  - Consult agents in fields you hadn't previously considered to try to derive more accurate conclusions and diagnostic opinions;  
  - This process may need to be repeated several times until you can arrive at a basically accurate diagnostic opinion. However, **do not repeat it too many times, as this will cause confusion in your memory.**;
- Finally, you need to summarize all the responses and information obtained above. Respond to the outpatient agent with an accurate diagnostic report.

#### Tools

**You should make good use of the provided tools to discover agents within the network.** You can also use the tools to search for information on the internet to assist your diagnosis. However, for specific conditions, if there are corresponding agents within the network, your first choice should be to request assistance from expert agents, as they have more extensive experience. If you find that there are no such experts within the network, you can try searching for them.
"""


class SpecialistHostExecutor(ExecutorBase):
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
            task.id, [{'role': 'system', 'content': SPECIALIST_HOST_PROMPT}])

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
