import asyncio
import logging
import threading
from dataclasses import dataclass

from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage, AssistantMessage, TextBlock

logger = logging.getLogger("claude-slack-bot")


@dataclass
class ClaudeResult:
    output: str
    session_id: str | None
    is_error: bool = False


_active_task: asyncio.Task | None = None
_cancel_event = threading.Event()


def cancel_active():
    global _active_task
    if _active_task and not _active_task.done():
        _cancel_event.set()
        _active_task.cancel()
        _active_task = None
        return True
    return False


def is_busy() -> bool:
    return _active_task is not None and not _active_task.done()


async def _run_prompt_async(prompt: str, cwd: str, session_id: str | None = None) -> ClaudeResult:
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        permission_mode="bypassPermissions",
        cwd=cwd,
    )
    if session_id:
        options.resume = session_id

    result_text_parts: list[str] = []
    result_session_id = session_id

    try:
        async for message in query(prompt=prompt, options=options):
            if _cancel_event.is_set():
                return ClaudeResult(output="Cancelled.", session_id=session_id, is_error=True)

            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        result_text_parts.append(block.text)

            elif isinstance(message, ResultMessage):
                result_session_id = message.session_id
                if message.result:
                    result_text_parts = [message.result]
                if message.is_error:
                    return ClaudeResult(
                        output=message.result or "Unknown error from Claude.",
                        session_id=result_session_id,
                        is_error=True,
                    )

        output = "\n".join(result_text_parts) if result_text_parts else "No output from Claude."
        return ClaudeResult(output=output, session_id=result_session_id)

    except asyncio.CancelledError:
        return ClaudeResult(output="Cancelled.", session_id=session_id, is_error=True)
    except Exception as e:
        logger.exception(f"Agent SDK error: {e}")
        return ClaudeResult(output=str(e), session_id=session_id, is_error=True)


def run_prompt(prompt: str, cwd: str, session_id: str | None = None) -> ClaudeResult:
    global _active_task
    _cancel_event.clear()

    loop = asyncio.new_event_loop()
    try:
        _active_task = loop.create_task(_run_prompt_async(prompt, cwd, session_id))
        result = loop.run_until_complete(_active_task)
    except asyncio.CancelledError:
        result = ClaudeResult(output="Cancelled.", session_id=session_id, is_error=True)
    finally:
        _active_task = None
        loop.close()

    return result
