import logging

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    InternalError,
    InvalidParamsError,
    Part,
    TaskState,
    TextPart,
    UnsupportedOperationError,
)
from a2a.utils import (
    new_agent_text_message,
    new_task,
)
from a2a.utils.errors import ServerError

from app.agent import CurrencyAgent

import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_METADATA_SESSION_KEY = "langfuse_session_id"


def _create_langfuse_callbacks():
    """Return Langfuse LangChain callbacks if tracing is enabled."""
    host = os.environ.get("LANGFUSE_HOST")
    enabled = os.environ.get("LANGFUSE_TRACING_ENABLED", "true").lower() != "false"
    if not host or not enabled:
        return []
    try:
        from langfuse.langchain import CallbackHandler

        return [CallbackHandler()]
    except Exception:
        logger.warning("Failed to initialize Langfuse callback handler", exc_info=True)
        return []


def _build_langfuse_metadata(session_id=None):
    """Build a metadata dict for LangGraph config that Langfuse picks up."""
    metadata = {}
    if session_id:
        metadata["langfuse_session_id"] = session_id
    return metadata


class CurrencyAgentExecutor(AgentExecutor):
    """Currency Conversion AgentExecutor Example."""

    def __init__(self):
        self.agent = CurrencyAgent()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        error = self._validate_request(context)
        if error:
            raise ServerError(error=InvalidParamsError())

        query = context.get_user_input()
        task = context.current_task

        # Extract Langfuse session ID from incoming A2A message metadata
        session_id = None
        if context.message and context.message.metadata:
            session_id = context.message.metadata.get(_METADATA_SESSION_KEY)
        callbacks = _create_langfuse_callbacks()
        langfuse_metadata = _build_langfuse_metadata(session_id=session_id)

        if not task:
            task = new_task(context.message)  # type: ignore
            await event_queue.enqueue_event(task)
        updater = TaskUpdater(event_queue, task.id, task.context_id)
        try:
            async for item in self.agent.stream(query, task.context_id, callbacks=callbacks, metadata=langfuse_metadata):
                is_task_complete = item['is_task_complete']
                require_user_input = item['require_user_input']

                if not is_task_complete and not require_user_input:
                    await updater.update_status(
                        TaskState.working,
                        new_agent_text_message(
                            item['content'],
                            task.context_id,
                            task.id,
                        ),
                    )
                elif require_user_input:
                    await updater.update_status(
                        TaskState.input_required,
                        new_agent_text_message(
                            item['content'],
                            task.context_id,
                            task.id,
                        ),
                        final=True,
                    )
                    break
                else:
                    await updater.add_artifact(
                        [Part(root=TextPart(text=item['content']))],
                        name='conversion_result',
                    )
                    await updater.complete()
                    break

        except Exception as e:
            logger.error(f'An error occurred while streaming the response: {e}')
            raise ServerError(error=InternalError()) from e

    def _validate_request(self, context: RequestContext) -> bool:
        return False

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        raise ServerError(error=UnsupportedOperationError())
