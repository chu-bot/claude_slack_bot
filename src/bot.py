import os
import logging
import threading
import time
from collections import deque
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from . import db
from . import claude_cli
from .formatter import format_response, truncate_for_slack

logger = logging.getLogger("claude-slack-bot")

app = App(token=os.environ["SLACK_BOT_TOKEN"])

_queue: deque[dict] = deque()
_queue_lock = threading.Lock()
_processing = False


def _resolve_username(client, user_id: str) -> str:
    try:
        result = client.users_info(user=user_id)
        return result["user"]["profile"].get("display_name") or result["user"]["real_name"]
    except Exception:
        return user_id


def _update_thinking(client, channel: str, ts: str, elapsed: int):
    minutes, seconds = divmod(elapsed, 60)
    if minutes > 0:
        time_str = f"{minutes}m{seconds}s"
    else:
        time_str = f"{seconds}s"

    suffix = ""
    if elapsed >= 300:
        suffix = " — this is taking a while, still working"

    client.chat_update(
        channel=channel,
        ts=ts,
        text=f"⏳ Thinking... ({time_str}){suffix}",
    )


def _process_message(client, channel_id: str, user_id: str, text: str, thread_ts: str | None):
    global _processing
    _processing = True

    try:
        logger.info(f"Processing message from {user_id}: {text[:80]}")
        username = _resolve_username(client, user_id)
        default_repo = os.environ.get("DEFAULT_REPO_PATH", os.getcwd())

        session = db.get_active_session(channel_id)
        if not session:
            db_id = db.create_session(channel_id, default_repo, text)
            session = db.get_session_by_id(db_id)
        else:
            db_id = session["id"]

        db.log_prompt(db_id, channel_id, user_id, username, text)

        reply = client.chat_postMessage(
            channel=channel_id,
            text="⏳ Thinking...",
            thread_ts=thread_ts,
        )
        thinking_ts = reply["ts"]

        timer_stop = threading.Event()

        def timer_loop():
            elapsed = 0
            while not timer_stop.is_set():
                time.sleep(15)
                elapsed += 15
                if timer_stop.is_set():
                    break
                try:
                    _update_thinking(client, channel_id, thinking_ts, elapsed)
                except Exception:
                    pass

        timer_thread = threading.Thread(target=timer_loop, daemon=True)
        timer_thread.start()

        result = claude_cli.run_prompt(
            prompt=text,
            cwd=session["repo_path"],
            session_id=session["session_id"],
        )

        timer_stop.set()

        if result.session_id and result.session_id != session.get("session_id"):
            db.update_session_claude_id(db_id, result.session_id)

        formatted = format_response(result.output, db_id, result.is_error)
        formatted = truncate_for_slack(formatted)

        db.update_prompt_response(db_id, text, formatted[:200])

        client.chat_update(
            channel=channel_id,
            ts=thinking_ts,
            text=formatted,
        )

    except Exception as e:
        logger.exception(f"Error processing message: {e}")
        try:
            client.chat_postMessage(
                channel=channel_id,
                text=f"❌ Bot error: {e}",
                thread_ts=thread_ts,
            )
        except Exception:
            pass
    finally:
        _processing = False
        _process_next(client)


def _process_next(client):
    with _queue_lock:
        if _queue and not _processing:
            item = _queue.popleft()
            thread = threading.Thread(
                target=_process_message,
                args=(client, item["channel"], item["user"], item["text"], item["thread_ts"]),
                daemon=True,
            )
            thread.start()


def _enqueue(client, channel_id: str, user_id: str, text: str, thread_ts: str | None):
    if _processing:
        with _queue_lock:
            pos = len(_queue) + 1
            _queue.append({"channel": channel_id, "user": user_id, "text": text, "thread_ts": thread_ts})
        client.chat_postMessage(
            channel=channel_id,
            text=f"⏳ Queued ({pos} ahead)",
            thread_ts=thread_ts,
        )
    else:
        thread = threading.Thread(
            target=_process_message,
            args=(client, channel_id, user_id, text, thread_ts),
            daemon=True,
        )
        thread.start()


@app.event("message")
def handle_message(event, client, say):
    if event.get("subtype"):
        return
    if event.get("bot_id"):
        return

    text = event.get("text", "").strip()
    if not text:
        return

    channel_id = event["channel"]
    user_id = event["user"]
    thread_ts = event.get("thread_ts", event["ts"])

    new_triggers = ["new session", "start over", "fresh start"]
    if any(t in text.lower() for t in new_triggers):
        _handle_new_session(client, channel_id, text, thread_ts)
        return

    _enqueue(client, channel_id, user_id, text, thread_ts)


def _handle_new_session(client, channel_id: str, text: str, thread_ts: str):
    default_repo = os.environ.get("DEFAULT_REPO_PATH", os.getcwd())
    db_id = db.create_session(channel_id, default_repo, text)
    client.chat_postMessage(
        channel=channel_id,
        text=f"✅ Started new session #{db_id}",
        thread_ts=thread_ts,
    )
