import subprocess
import json
import re
import os
import signal
from dataclasses import dataclass


@dataclass
class ClaudeResult:
    output: str
    session_id: str | None
    is_error: bool = False


_active_process: subprocess.Popen | None = None


def cancel_active():
    global _active_process
    if _active_process and _active_process.poll() is None:
        os.killpg(os.getpgid(_active_process.pid), signal.SIGTERM)
        _active_process = None
        return True
    return False


def run_prompt(prompt: str, cwd: str, session_id: str | None = None) -> ClaudeResult:
    global _active_process

    cmd = ["claude", "-p", prompt, "--output-format", "json"]
    if session_id:
        cmd += ["--resume", session_id]

    try:
        _active_process = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=os.setsid,
        )
        stdout, stderr = _active_process.communicate()
        _active_process = None

        if not stdout.strip():
            return ClaudeResult(
                output=stderr.strip() or "No output from Claude.",
                session_id=session_id,
                is_error=True,
            )

        try:
            data = json.loads(stdout)
            result_text = data.get("result", stdout)
            parsed_session_id = data.get("session_id", session_id)
            return ClaudeResult(output=result_text, session_id=parsed_session_id)
        except json.JSONDecodeError:
            return ClaudeResult(output=stdout.strip(), session_id=session_id)

    except Exception as e:
        _active_process = None
        return ClaudeResult(output=str(e), session_id=session_id, is_error=True)


def is_busy() -> bool:
    return _active_process is not None and _active_process.poll() is None
