import os
import subprocess
from slack_bolt import App

from . import db
from . import claude_cli
from .formatter import format_response, truncate_for_slack


def register_commands(app: App):
    @app.command("/new")
    def handle_new(ack, command, client):
        ack()
        channel_id = command["channel_id"]
        text = command.get("text", "").strip() or "New session"
        default_repo = os.environ.get("DEFAULT_REPO_PATH", os.getcwd())
        db_id = db.create_session(channel_id, default_repo, text)
        client.chat_postMessage(
            channel=channel_id,
            text=f"✅ Started new session #{db_id}",
        )

    @app.command("/history")
    def handle_history(ack, command, client):
        ack()
        channel_id = command["channel_id"]
        sessions = db.get_recent_sessions(channel_id)
        active = db.get_active_session(channel_id)

        if not sessions:
            client.chat_postMessage(channel=channel_id, text="No sessions yet.")
            return

        lines = ["*Recent Sessions:*"]
        for s in sessions:
            age = _format_age(s["last_active"])
            prompt = (s["first_prompt"] or "")[:60]
            count = s["message_count"]
            marker = " ← active" if active and s["id"] == active["id"] else ""
            lines.append(f"• *#{s['id']}* [{age}] \"{prompt}\" — {count} messages{marker}")

        client.chat_postMessage(channel=channel_id, text="\n".join(lines))

    @app.command("/load")
    def handle_load(ack, command, client):
        ack()
        channel_id = command["channel_id"]
        text = command.get("text", "").strip()

        if not text or not text.isdigit():
            client.chat_postMessage(
                channel=channel_id,
                text="Usage: `/load <session_id>` — get IDs from `/history`",
            )
            return

        session_db_id = int(text)
        session = db.get_session_by_id(session_db_id)

        if not session:
            client.chat_postMessage(channel=channel_id, text=f"Session #{session_db_id} not found.")
            return

        db.set_active_session(channel_id, session_db_id)
        prompt = (session["first_prompt"] or "")[:60]
        repo = os.path.basename(session["repo_path"])
        client.chat_postMessage(
            channel=channel_id,
            text=f"✅ Switched to session #{session_db_id} — \"{prompt}\" (repo: {repo})",
        )

    @app.command("/cancel")
    def handle_cancel(ack, command, client):
        ack()
        channel_id = command["channel_id"]
        if claude_cli.cancel_active():
            client.chat_postMessage(channel=channel_id, text="🛑 Cancelled active task.")
        else:
            client.chat_postMessage(channel=channel_id, text="Nothing running right now.")

    @app.command("/jumpstart")
    def handle_jumpstart(ack, command, client):
        ack()
        channel_id = command["channel_id"]
        project_name = command.get("text", "").strip()

        if not project_name:
            client.chat_postMessage(
                channel=channel_id,
                text="Usage: `/jumpstart <project-name>`",
            )
            return

        thinking = client.chat_postMessage(
            channel=channel_id,
            text=f"⏳ Creating mokadoe/{project_name}...",
        )

        try:
            projects_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "projects")
            os.makedirs(projects_dir, exist_ok=True)
            local_path = os.path.join(projects_dir, project_name)

            # Create repo with a README so it has an initial commit
            create_result = subprocess.run(
                ["gh", "repo", "create", f"mokadoe/{project_name}", "--private", "--add-readme"],
                capture_output=True, text=True,
            )
            if create_result.returncode != 0:
                raise RuntimeError(create_result.stderr.strip())

            import time
            time.sleep(2)

            clone_result = subprocess.run(
                ["git", "clone", f"git@github.com:mokadoe/{project_name}.git", local_path],
                capture_output=True, text=True,
            )
            if clone_result.returncode != 0:
                raise RuntimeError(clone_result.stderr.strip())

            repo_url = f"https://github.com/mokadoe/{project_name}"

            db_id = db.create_session(channel_id, local_path, f"jumpstart {project_name}")

            result = claude_cli.run_prompt(
                prompt=f"Initialize this as a new Python project with uv. Create a basic project structure with pyproject.toml, src/ directory, .gitignore, and a README. Then git add, commit, and push.",
                cwd=local_path,
            )

            if result.session_id:
                db.update_session_claude_id(db_id, result.session_id)

            client.chat_update(
                channel=channel_id,
                ts=thinking["ts"],
                text=f"📋 New project: {project_name}  [Session #{db_id}]\n\n• Created `mokadoe/{project_name}` on GitHub\n• Scaffolded and pushed initial structure\n\n→ {repo_url}\n🌿 main",
            )

        except Exception as e:
            client.chat_update(
                channel=channel_id,
                ts=thinking["ts"],
                text=f"❌ Failed to create project: {e}",
            )


def _format_age(timestamp_str: str) -> str:
    if not timestamp_str:
        return "unknown"
    from datetime import datetime, timezone
    try:
        ts = datetime.fromisoformat(timestamp_str)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = now - ts
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return "just now"
        if seconds < 3600:
            return f"{seconds // 60}m ago"
        if seconds < 86400:
            return f"{seconds // 3600}h ago"
        return f"{seconds // 86400}d ago"
    except Exception:
        return "unknown"
