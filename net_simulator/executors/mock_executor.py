
import asyncio
import uuid
from net_simulator.executors.executor_base import ExecutorBase
from a2a.utils import new_task, new_agent_text_message
from a2a.types import TaskArtifactUpdateEvent, Artifact, TextPart, TaskState
from a2a.server.tasks import TaskUpdater
from uuid import uuid4


class MockExecutor(ExecutorBase):

    async def execute(self, context, event_queue):
        task = context.current_task
        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)

        self.logger.info(f"User input: {context.get_user_input(delimiter=' ')}")
        updater = TaskUpdater(event_queue, task.id, task.contextId)

        await updater.start_work(new_agent_text_message(
            text='Starting mock task...',
            context_id=task.contextId,
            task_id=task.id
        ))

        artifact_id = str(uuid4())

        for i in range(10):
            await event_queue.enqueue_event(
                TaskArtifactUpdateEvent(
                    artifact=Artifact(
                        name='Mock Artifact',
                        parts=[TextPart(text=f"Mock message {i + 1}")],
                        artifactId=artifact_id,
                    ),
                    taskId=task.id,
                    contextId=task.contextId,
                    append=True if i > 0 else False,
                    lastChunk=True if i == 9 else False
                )
            )
            self.logger.info(f"Task({task.id}) -> Mock message {i + 1} sent.")
            await updater.update_status(state=TaskState.working)
            await asyncio.sleep(0.5)

        await updater.complete()

    async def cancel(self, context, event_queue):
        raise NotImplementedError()
