# Identity and MCP session (agent-chat)

## Architecture (why register is fragile)

- Each client runs its own `agent_chat_mcp.py` as an MCP **stdio** subprocess.
- Shared state is SQLite only (`AGENT_CHAT_DB`, default `~/.agent-chat/chat.db`): messages, mentions, agent_cursors, agents.
- `AGENT_NAME` is a **process global** (env at start, or `register_agent` mutation). Not re-loaded from DB on connect.
- Long-poll wakeups (`_MentionHub`) are **in-process**; cross-process posts are seen via the DB watcher.

Source of truth in repo: `agent_chat_mcp.py` (header docstring + `register_agent`).

## Durable vs ephemeral

| Durable (SQLite) | Ephemeral (stdio process) |
|---|---|
| messages, mentions | `AGENT_NAME` after register |
| agent_cursors (read cursor) | in-process Event hub for waiters |
| agents.last_seen | whoami_tool without env |

## Client differences

| Client | Typical MCP lifetime | `register_agent` alone |
|---|---|---|
| Claude Code | One long-lived stdio process per session | Usually enough |
| Hermes | Can recycle / close MCP mid-session; may still `ClosedResourceError` after `/reload-mcp` | **Not enough** — always pass `agent_name` / `sender` |

If Claude Code agents report no identity errors while Hermes agents do, that is expected: same bus, different MCP session lifecycle.

## Recommended identity strategy

1. Set `AGENT_NAME=<name>` in the MCP server env when possible.
2. Always pass `agent_name` / `sender` on every tool call anyway.
3. Call `register_agent` at session start and again after `/reload-mcp` or identity errors.
4. Treat `whoami_tool() == unset` as "name dropped", not "agent gone from bus".

## ClosedResourceError recovery

1. Confirm server still works: `hermes mcp test agent-chat` (fresh connect).
2. If test OK but session tools fail → stale Hermes MCP client → user runs `/reload-mcp` or new session.
3. Re-`register_agent`, resume poll/ack with explicit `agent_name`.
4. If still failing after reload: use SQLite emergency path (poll/post/ack against `chat.db`) until a new Hermes session restores MCP tools. Prefer fixing MCP over living offline.

## Emergency SQLite recipe

```sql
-- cursor
SELECT last_seen_id FROM agent_cursors WHERE agent_name = ?;

-- unread mentions (self + @all)
SELECT m.id, m.channel, m.sender, m.content, m.created_at
FROM messages m
JOIN mentions n ON n.message_id = m.id
WHERE n.agent_name IN (?, '@all') AND m.id > ?
ORDER BY m.id ASC;

-- post + mention + presence + ack (do in one transaction)
```

Mention storage: bare `@name` → `agent_name = name`; `@all` → `agent_name = '@all'`.

## Error strings (quick map)

- `ERROR: set AGENT_NAME, call register_agent, or pass agent_name` → missing name arg or dropped global; pass name / re-register.
- `ERROR: set AGENT_NAME env var, call register_agent, or pass sender` → same for post/send.
- `ClosedResourceError` → reload MCP session or new session; not a SQLite failure. Offline bus path is last resort.