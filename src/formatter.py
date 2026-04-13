import re


def format_response(output: str, session_id: int, is_error: bool = False) -> str:
    if is_error:
        return f"❌ [Session #{session_id}]\n\n{output}"

    has_code_changes = _detect_code_changes(output)

    if has_code_changes:
        title, bullets, branch, files_changed = _parse_code_response(output)
        lines = [f"📋 {title}  [Session #{session_id}]", ""]
        for b in bullets:
            lines.append(f"• {b}")
        lines.append("")
        meta_parts = []
        if branch:
            meta_parts.append(f"🌿 {branch}")
        if files_changed:
            meta_parts.append(files_changed)
        if meta_parts:
            lines.append(" · ".join(meta_parts))
        return "\n".join(lines)

    return f"💬 [Session #{session_id}]\n\n{output}"


def _detect_code_changes(output: str) -> bool:
    indicators = [
        r"commit[ted]*\s",
        r"created?\s+(file|PR|branch)",
        r"modified\s+",
        r"added\s+",
        r"files?\s+changed",
        r"wrote\s+to\s+",
        r"updated?\s+.*\.(py|ts|js|tsx|jsx|css|html|md)",
    ]
    lower = output.lower()
    return any(re.search(p, lower) for p in indicators)


def _parse_code_response(output: str) -> tuple[str, list[str], str, str]:
    lines = output.strip().split("\n")
    title = lines[0][:80] if lines else "Changes"

    bullets = []
    for line in lines:
        line = line.strip()
        if line.startswith(("- ", "* ", "• ")):
            bullets.append(line.lstrip("-*• ").strip())
    if not bullets:
        sentences = re.split(r'[.!\n]', output)
        bullets = [s.strip() for s in sentences[:3] if s.strip()]

    branch = ""
    branch_match = re.search(r'(?:branch|🌿)\s*[:`]?\s*(\S+)', output, re.IGNORECASE)
    if branch_match:
        branch = branch_match.group(1).strip("`")

    files_match = re.search(r'(\d+)\s+files?\s+changed', output, re.IGNORECASE)
    files_changed = files_match.group(0) if files_match else ""

    return title, bullets, branch, files_changed


def truncate_for_slack(text: str, max_length: int = 3900) -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length] + "\n\n... _(truncated — response too long for Slack)_"
