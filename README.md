# Claude Slack Bot

A Slack bot that lets your team build software by chatting. Every message in the channel gets routed to Claude Code CLI, which writes code, commits, and pushes — nobody touches files directly.

## How It Works

```
Family member types in Slack
  → Bot posts "⏳ Thinking..."
    → Claude Code writes/modifies code
      → Bot edits its message with a structured summary
        → Code is committed and pushed to GitHub
```

**Thread replies resume context.** Reply in a thread and the bot picks up where that conversation left off — same Claude session, same repo state.

**One task at a time.** If Claude is busy, your message queues automatically. No conflicts, no race conditions.

## Quick Start

```bash
# Clone and install
git clone git@github.com:chu-bot/claude_slack_bot.git
cd claude_slack_bot
uv sync

# Configure
cp .env.example .env
# Fill in your tokens (see Setup below)

# Run
uv run python main.py
```

## Setup

### 1. Slack App

Create an app at [api.slack.com/apps](https://api.slack.com/apps):

- **Socket Mode**: ON → generate App-Level Token (`xapp-...`)
- **Bot Token Scopes**: `chat:write`, `channels:history`, `groups:history`, `users:read`, `commands`
- **Event Subscriptions**: `message.channels`, `message.groups`
- **Slash Commands**: `/new`, `/history`, `/load`, `/cancel`, `/jumpstart`
- **Install to workspace** → copy Bot Token (`xoxb-...`)

### 2. GitHub

- `gh` CLI authenticated with org access: `gh auth login`
- If creating repos under an org: `gh auth refresh -s admin:org`

### 3. Claude Code

- `claude` CLI installed and authenticated (`claude auth login`)

### 4. Environment Variables

```
SLACK_BOT_TOKEN=xoxb-...        # Bot OAuth token
SLACK_APP_TOKEN=xapp-...        # Socket Mode token
GH_TOKEN=gho_...                # GitHub token (from `gh auth token`)
DEFAULT_REPO_PATH=/path/to/repo # Default working directory
```

## Commands

| Command | What it does |
|---------|-------------|
| `/new` | Start a fresh Claude session |
| `/history` | List recent sessions with IDs |
| `/load <id>` | Switch to a previous session |
| `/cancel` | Kill the running Claude task |
| `/jumpstart <name>` | Create a new `mokadoe/<name>` repo, scaffold it, start a session |

You can also trigger a new session by saying "new session", "start over", or "fresh start" in a message.

## Architecture

```
main.py              # Entrypoint, reconnection loop, logging setup
src/
  bot.py             # Slack message handler, queue, thinking timer
  claude_cli.py      # Subprocess wrapper for `claude` CLI
  commands.py        # Slash command handlers (/new, /history, /load, /cancel, /jumpstart)
  db.py              # SQLite: sessions, thread mappings, prompt log
  formatter.py       # Response card formatting (code changes vs informational)
data/
  bot.db             # SQLite database (gitignored)
  bot.log            # Log file (gitignored)
projects/            # Cloned repos from /jumpstart (gitignored)
```

## Session Model

- **One active session** per channel at a time
- **Thread replies** automatically resume the session that was used in that thread
- **Top-level messages** go to the active session
- `/load` switches the active session; `/new` creates a fresh one
- Sessions store: Claude session ID (for `--resume`), repo path, first prompt, timestamps

## Response Format

The bot adapts its response based on what Claude did:

**Code changes** — structured card with title, bullet points, branch, files changed

**Questions/explanations** — plain text with session ID

**Errors** — error message with session ID

Session ID is always visible so everyone knows which context they're in.

## Deployment

Currently runs locally. Planned: Oracle Cloud Free Tier (forever-free ARM VM).

```bash
# Keep it running in tmux
tmux new -s bot
uv run python main.py
# Ctrl+B, D to detach
```

The bot auto-reconnects on broken pipes and logs everything to `data/bot.log`.

## Contributing

Read `SPEC.md` for the full technical spec. Read `AI_CONTEXT.md` for working with Claude Code on this project.
