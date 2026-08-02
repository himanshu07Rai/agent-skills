---
name: agent-chat
description: Join the shared agent-chat bus — register, wait for @mentions, act, reply.
user-invocable: true
argument-hint: "agent-name"
---

# agent-chat

Shared SQLite chat bus (MCP tools) so multiple agents message each other with `@mentions`.

## Setup (once per session)

1. Get your name from the user (or `$ARGUMENTS`), e.g. `worker`, `claude-backend`.
2. Call once:

```
register_agent(name="<your-name>")
```

3. Prefer also setting `AGENT_NAME=<your-name>` in the MCP server env (Hermes `hermes mcp` config) so identity survives process restarts. Do not rely on register alone under Hermes.

Optional: list who else is around with `list_agents()`.

## Main loop (push, don't busy-poll)

**Always pass your name on every call** (`agent_name` / `sender`). Under Hermes, process-local registration often drops between tool calls even in the same chat session.

```
NAME = "<your-name>"
register_agent(name=NAME)
while the user has not said stop:
 1. result = poll_mentions(agent_name=NAME, wait_seconds=30)
    # blocks until @you or @all (or timeout)
 2. if result is "No new mentions...": loop
 3. Read each message. Note last_seen_id from the footer line:
      [last_seen_id: N]
 4. Act on directives / questions / status requests using your tools.
 5. Reply with post_message(sender=NAME, body="@requester <your reply>")
    - mention the requester so they get notified
    - use @all only when everyone should see it
 6. ack_mentions(agent_name=NAME, up_to_id=N)   # always after you finished processing
 7. On "ERROR: set AGENT_NAME...": re-register, then retry with explicit name args
 8. On ClosedResourceError: see Pitfalls — do not spin the same failing MCP call
```

That is the whole protocol. Cursor never auto-advances — if you crash before `ack_mentions`, you re-read on retry (good). Bus state (messages, cursors) lives in SQLite and is durable; only the in-process `AGENT_NAME` global is not.

## During long work

Between major steps, non-blocking check:

```
poll_mentions(agent_name=NAME, wait_seconds=0)
```

- new instruction that changes the task → integrate it, then ack
- cancel ("stop", "nevermind") → stop, ack, reply
- unrelated new task → finish current work first, then handle

## Tools cheat sheet

| Tool | Use |
|---|---|
| `register_agent(name)` | at start; re-call if identity errors |
| `post_message(sender, body)` | send; always pass `sender`; put `@name` or `@all` in body |
| `poll_mentions(agent_name, wait_seconds=30)` | wait for work; always pass `agent_name` |
| `ack_mentions(agent_name, up_to_id)` | mark processed; always pass `agent_name` |
| `list_agents()` | who is on the bus |
| `whoami_tool()` | confirm process-local name (may be empty if identity dropped) |

Older channel tools (`send_message`, `read_messages`, `wait_for_mention`) still work; prefer the table above.

## Rules of thumb

- **Always pass name args** (`agent_name` / `sender`) — do not depend on a prior `register_agent` alone under Hermes.
- **Always @ someone** when the reply needs a reaction — otherwise no one is notified.
- **Always ack** after handling a batch (`up_to_id` = the `last_seen_id` from the poll result).
- **Post outcomes** back to the requester (or `@boss` if the human is driving via the web viewer).
- **Stay in the loop** until the user says stop / quit / disconnect.

## Pitfalls (Hermes + identity)

- **Process-local identity.** `agent_chat_mcp` is one MCP stdio subprocess per client. `register_agent` only sets an in-process `AGENT_NAME` global (+ `agents.last_seen` in SQLite). It does **not** restore identity when the stdio process restarts. The `agents` table is presence, not "my name for this connection".
- **Claude Code vs Hermes.** Claude Code typically keeps one long-lived MCP stdio process for the session, so `register_agent` once "just works". Hermes can recycle or detach the MCP client mid-session — identity errors and `ClosedResourceError` are expected here even when Claude Code clients on the same bus see none.
- **Hermes can drop identity mid-session.** Even without an explicit reload, a later `poll_mentions` without `agent_name` may return `ERROR: set AGENT_NAME, call register_agent, or pass agent_name`. Fix: always pass names; re-register on that error.
- **`ClosedResourceError` on MCP tools.** In-session MCP client is stale while `hermes mcp test agent-chat` still works from a fresh connect. Ask the user to run `/reload-mcp` (or start a **new** session). If tools still fail after reload, stay offline via SQLite fallback (below) rather than retrying the same MCP call forever.
- **Do not treat identity drop / ClosedResourceError as "bus is down".** Cursors/messages in `~/.agent-chat/chat.db` remain valid. After MCP recovers, resume with the same name and existing cursor.

## Emergency offline path (SQLite)

Use only when MCP tools keep failing (`ClosedResourceError`) but the bus must keep moving, and the user has approved shell access:

- DB: `~/.agent-chat/chat.db` (or `$AGENT_CHAT_DB`)
- Tables: `messages(channel, sender, content, created_at)`, `mentions(message_id, agent_name)`, `agent_cursors`, `agents`
- Poll: join `messages` + `mentions` where `agent_name IN (NAME, '@all')` and `id > cursor`
- Post: insert message, insert mention rows for each `@target` / store `@all` as agent_name `'@all'`, update `agents.last_seen`
- Ack: set `agent_cursors.last_seen_id = max(current, N)`

Prefer restoring MCP over living on this path. Full design notes: `references/identity-and-mcp.md`.

## Human / BOSS side

Web viewer (same DB):

```
python3 agent_chat_viewer.py --port 8765
# open http://localhost:8765
```

Post as `boss` with `@your-agent ...` in the body. Agents pick it up via `poll_mentions`.