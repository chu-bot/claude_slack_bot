# Claude Slack Bot — Spec

## Channel Guidelines

Pin these in the Slack channel:

**How this channel works:**
- Every message here goes to Claude. Just type what you want built or changed.
- One session runs at a time. If Claude is busy, your message queues automatically.
- Check `/history` to see what's been worked on. Use `/load <id>` to switch back to a previous session.
- Use `/new` when you want to start fresh. Use `/jumpstart <name>` to spin up a whole new project.
- Claude commits directly — no PRs, no approvals. If something breaks, just ask Claude to fix it.
- Don't work on the same files as someone else at the same time. Check `/history` to see what's active.
- Use threads for follow-ups on the same task. Top-level messages are new prompts to the active session.

## Overview

A Slack bot that bridges a Slack channel to Claude Code CLI. Messages in the channel are piped to isolated Claude Code sessions. The bot manages session lifecycle, posts results back to Slack, and provides slash commands for session control.

## Core Behavior

### Message Flow

1. User sends a message in the Slack channel (or thread)
2. Bot immediately posts a reply: "⏳ Thinking..." (with a loading indicator)
3. Bot spawns `claude -p "<message>" --output-format text` in the background, scoped to the active session's repo
4. While running, bot edits its message every ~15s with an elapsed timer: "⏳ Thinking... (30s)", "⏳ Thinking... (45s)"
5. When Claude finishes, bot **edits its own message** with the response
6. If output is too long for Slack (>4000 chars), truncate with a "View full output" link or thread continuation

### Response Formats

Responses adapt based on what Claude did:

**Code changes:**
```
📋 Dark mode toggle  [Session #3]

• Added ThemeToggle component with light/dark switch
• CSS variables for color palettes in globals.css
• Persists preference in localStorage

🌿 feat/dark-mode · 3 files changed · 2 commits
```

**Informational / read-only:**
```
💬 [Session #3]

The auth module uses JWT tokens stored in httpOnly cookies.
The refresh logic is in `lib/auth.ts:42`...
```

**Error:**
```
❌ [Session #3]

Claude encountered an error: <error message>
```

The session ID is always visible so everyone knows which context they're in.

### Session Model

There is **one active session** at a time across the channel. Think of it like a shared terminal — people pop in when they have time and contribute to whatever the current session is working on.

- The **active session** persists until someone explicitly starts a new one (`/new`) or loads a different one (`/load`).
- All messages in the channel go to the active session, regardless of threading.
- Sessions map 1:1 to a Claude Code session ID and a repo path.
- Sessions are **isolated** from any personal Claude Code sessions running elsewhere.
- Processing is **sequential** — if a message comes in while Claude is working, it queues and the user sees "⏳ Queued (1 ahead)". When the current task finishes, the next one starts automatically.

### Direct Commits, No PRs

Claude commits directly to the working branch. There is no PR/review/merge flow — this is a shared collaborative workspace. Everyone trusts the bot and each other. If something breaks, fix it with the next prompt.

## Slash Commands

### `/new`

Start a fresh session on the current repo (or specify a different repo path). Becomes the active session.

**Also triggered by:** messages containing "new session", "start over", "fresh start"

### `/history`

List recent sessions with their IDs, first prompt, and message count:

```
Recent Sessions:
• #1 [2h ago] "Add dark mode toggle" — 3 messages
• #2 [5h ago] "Fix auth bug" — 7 messages
• #3 [1d ago] "Set up CI pipeline" — 12 messages

Active: #1
```

### `/load <id>`

Switch the active session. Takes a session ID from `/history`. All future messages resume that session's Claude context and repo.

Example: `/load 2` → "✅ Switched to session #2 — Fix auth bug (repo: mokadoe/family-app)"

### `/jumpstart <project-name>`

1. Creates a new GitHub repo under the `mokadoe` organization: `mokadoe/<project-name>`
2. Clones it locally into `projects/<project-name>/` within the bot directory
3. Runs Claude Code to scaffold the project
4. Pushes initial commit to the new repo
5. Creates a new session pointing at the cloned repo and makes it the active session
6. Posts the repo URL back to Slack

## Technical Details

### Stack

- **Python 3.14** with `uv`
- **slack-bolt** — Slack bot framework (Socket Mode)
- **subprocess** — shells out to `claude` CLI
- **SQLite** — session and prompt log storage

### Environment Variables

```
SLACK_BOT_TOKEN     — xoxb-... bot token
SLACK_APP_TOKEN     — xapp-... for Socket Mode
GITHUB_TOKEN        — for /jumpstart repo creation
DEFAULT_REPO_PATH   — default working directory for Claude sessions
```

### Claude CLI Interface

```bash
# New session
claude -p "user message" --output-format text --cwd /path/to/repo

# Resume session
claude -p "user message" --resume <session_id> --output-format text --cwd /path/to/repo
```

Session ID is captured from Claude's output on first invocation and stored in SQLite.

### Project Directory Structure

```
claude_slack_bot/
├── projects/              # Cloned repos from /jumpstart
│   ├── family-recipes/
│   └── family-app/
├── data/
│   └── bot.db             # SQLite database
├── src/
│   └── ...
├── .env
└── ...
```

### Database Schema

```sql
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    repo_path TEXT,
    channel_id TEXT,
    first_prompt TEXT,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE prompt_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    channel_id TEXT,
    slack_user_id TEXT,
    slack_username TEXT,
    prompt TEXT,
    response_summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
```

### Prompt Log

Every message sent to the bot is logged to `prompt_log`. This provides a full audit trail of who asked what and when. The log is queryable via SQLite and can be exported.

### Long-Running Task Strategy

Claude Code sessions for real work can take minutes. The bot handles this with:

1. **Elapsed timer** — edits the "Thinking..." message every ~15s so users know it's alive
2. **No hard timeout** — sessions run until Claude finishes; real work takes time
3. **Soft warning at 5min** — appends "(this is taking a while — still working)" to the status
4. **`/cancel`** — kills the running Claude process and posts what it had so far
5. **Graceful queue** — if someone sends a message while Claude is working, they see "⏳ Queued (1 ahead)" and it runs next

### Error Handling

- If Claude CLI fails, edit the "Thinking..." message to show the error with session ID
- If Slack message edit fails, post a new message instead

## Future Considerations

- **Conflict handling:** Multiple sessions working on overlapping files in the same repo could cause git conflicts. Currently out of scope — coordinate via `/history` and session switching. Revisit if this becomes a pain point.

## Non-Goals

- No web UI
- No PR/review flow — direct commits
- No concurrent sessions — sequential processing
- No user authentication beyond Slack channel membership
- No interaction with personal Claude Code sessions
