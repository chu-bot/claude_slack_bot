# Claude Slack Bot

## Purpose

Slack bot that bridges a Slack channel to Claude Code CLI. Family/team members type what they want built in Slack, the bot pipes it to `claude -p`, and posts results back. Nobody touches code directly.

## Architecture

**Message flow:** Slack event → `bot.py` handler → queue → `claude_cli.py` subprocess → `formatter.py` → Slack message edit

**Session management:** SQLite tracks sessions (Claude session IDs + repo paths). One active session per channel. Thread replies auto-resume the session used in that thread via `thread_sessions` table.

**Sequential processing:** One Claude task runs at a time. Additional messages queue with visible position. No concurrency issues.

## Key Files

- `main.py` — Entrypoint. Loads env, inits DB, starts Socket Mode with auto-reconnect loop.
- `src/bot.py` — Core message handler. Manages queue, thinking timer, session resolution (thread → active → new).
- `src/claude_cli.py` — Wraps `claude -p` subprocess. Handles `--resume`, JSON output parsing, process cancellation.
- `src/commands.py` — Slash commands: `/new`, `/history`, `/load`, `/cancel`, `/jumpstart`. Jumpstart uses `gh` CLI.
- `src/db.py` — SQLite layer. Tables: `sessions`, `thread_sessions`, `prompt_log`.
- `src/formatter.py` — Detects code changes vs informational responses. Formats structured cards for Slack.

## Patterns & Conventions

- `claude -p` with `--output-format json` for machine-readable output, `--resume` for session continuity
- Bot edits its own "Thinking..." message rather than posting new ones
- All errors caught and posted to Slack with session ID
- `gh` CLI for GitHub operations (not PyGithub) — uses whatever auth the host machine has
- Logging to both `data/bot.log` and console

## Current State

Working end-to-end: messages → Claude → responses in Slack. Jumpstart creates repos under `mokadoe` org. Thread context resumption implemented. Logging in place. Deployment target: Oracle Cloud Free Tier.

## How to Work Here

- `.env` has all secrets (gitignored). Copy `.env.example` to start.
- `data/` and `projects/` are gitignored — runtime artifacts only.
- Test by running `uv run python main.py` and sending messages in the `#claude-project` Slack channel.
- The bot needs `claude` CLI authenticated on whatever machine it runs on.
- SQLite DB auto-creates on first run. Delete `data/bot.db` to reset all sessions.
