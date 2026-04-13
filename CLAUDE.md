# Claude Slack Bot

## Response Style

- Keep responses SHORT. Lead with what changed, not how you thought about it.
- Use the structured card format for completed work:
  ```
  📋 <title>

  • Bullet point of what changed
  • Another change

  → PR #N · N files changed
  🌿 branch-name → main
  ```
- Always include the current branch name in responses that touch code.
- No preamble, no "Sure!", no "Let me help you with that."

## Git

- Always track and report the branch name.
- Branch naming: `feat/<short-name>`, `fix/<short-name>`, `chore/<short-name>`
- Conventional commits: `type(scope): description`

## Code Style

- Python 3.14, use `uv` for dependencies.
- Minimal comments — only when logic is non-obvious.
- Prefer small, focused changes.
