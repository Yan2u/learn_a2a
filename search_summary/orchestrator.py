import uvicorn
from dotenv import load_dotenv
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    SendMessageRequest,
    SendStreamingMessageRequest,
    TaskState,
    TextPart,
    MessageSendParams,
)
from a2a.client import A2AClient, A2ACardResolver
from a2a.server.tasks import TaskUpdater
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message
import httpx
import os
from uuid import uuid4


class OrchestratorExecutor(AgentExecutor):

    searcher_client: A2AClient | None = None
    summarizer_client: A2AClient | None = None

    searcher_httpx_client: httpx.AsyncClient | None = None
    summarizer_httpx_client: httpx.AsyncClient | None = None

    async def initialize_agents(self):
        searcher_url = f'http://localhost:{os.getenv("SEARCHER_PORT", 8000)}'
        self.searcher_httpx_client = httpx.AsyncClient(
            base_url=searcher_url, timeout=1800)
        searcher_card = await A2ACardResolver(httpx_client=self.searcher_httpx_client, base_url=searcher_url).get_agent_card()
        self.searcher_client = A2AClient(
            httpx_client=self.searcher_httpx_client, agent_card=searcher_card)

        summarizer_url = f'http://localhost:{os.getenv("SUMMARIZER_PORT", 8001)}'
        self.summarizer_httpx_client = httpx.AsyncClient(
            base_url=summarizer_url, timeout=1800)
        summarizer_card = await A2ACardResolver(httpx_client=self.summarizer_httpx_client, base_url=summarizer_url).get_agent_card()
        self.summarizer_client = A2AClient(
            httpx_client=self.summarizer_httpx_client, agent_card=summarizer_card)

    async def execute(self, context: RequestContext, event_queue: EventQueue):
        if self.searcher_client is None:
            await self.initialize_agents()

        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        if not context.current_task:
            await updater.update_status(TaskState.submitted)
        await updater.update_status(TaskState.working, new_agent_text_message(
            text="Starting search and summarization process...\n",
            context_id=context.context_id,
            task_id=context.task_id
        ))
        texts = [x.root.text for x in context.message.parts if isinstance(
            x.root, TextPart)]
        print(texts)
        msg = ' '.join(texts)

        searcher_message = {
            'message': {
                'role': 'user',
                'parts': [
                    {'kind': 'text', 'text': msg}
                ],
                'messageId': uuid4().hex,
            },
        }

        searcher_req = SendMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(**searcher_message)
        )

        response = await self.searcher_client.send_message(searcher_req)

        if not response.root.result.parts:
            await updater.update_status(TaskState.failed, new_agent_text_message(
                text="Search failed, no response received.\n",
                context_id=context.context_id,
                task_id=context.task_id
            ))
            return

        print(response.root.result.parts[0].root.text)

        await updater.update_status(TaskState.working, new_agent_text_message(
            text="Search finished, Starting summarization process...\n",
            context_id=context.context_id,
            task_id=context.task_id
        ))

        summarizer_message = {
            'message': {
                'role': 'user',
                'parts': [
                    {'kind': 'text',
                        'text': response.root.result.parts[0].root.text}
                ],
                'messageId': uuid4().hex,
            },
        }

        summarizer_req = SendStreamingMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(**summarizer_message)
        )

        response = self.summarizer_client.send_message_streaming(
            summarizer_req)

        async for chunk in response:
            if chunk.root.result.status.message:
                await updater.update_status(
                    TaskState.working,
                    new_agent_text_message(
                        text=chunk.root.result.status.message.parts[0].root.text,
                        context_id=context.context_id,
                        task_id=context.task_id,
                    )
                )

        await updater.update_status(TaskState.completed, new_agent_text_message(
            text="\nSummarization completed.\n",
            context_id=context.context_id,
            task_id=context.task_id
        ))

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        raise Exception('cancel not supported')


class OrchestratorAgent:

    def run(self, port: int):
        url = f'http://127.0.0.1:{port}'
        skill = AgentSkill(
            id='search_and_summarize',
            name='Search and summarize results',
            description='Searches Bing for the given query and summarizes the results in Markdown format.',
            tags=['search', 'summarize', 'orchestrator'],
        )

        card = AgentCard(
            name='Search and Summarize Agent',
            description='Orchestrates search and summarization of web results.',
            url=url,
            version='0.1.0',
            defaultInputModes=['text'],
            defaultOutputModes=['text'],
            capabilities=AgentCapabilities(streaming=True),
            skills=[skill],
            supportsAuthenticatedExtendedCard=False
        )

        request_handler = DefaultRequestHandler(
            agent_executor=OrchestratorExecutor(),
            task_store=InMemoryTaskStore()
        )

        server = A2AStarletteApplication(
            agent_card=card,
            http_handler=request_handler,
        )

        uvicorn.run(server.build(), host='0.0.0.0', port=port)


if __name__ == "__main__":
    load_dotenv()
    port = int(os.getenv("ORCHESTRATOR_PORT", 8002))
    orchestrator_agent = OrchestratorAgent()
    orchestrator_agent.run(port)
