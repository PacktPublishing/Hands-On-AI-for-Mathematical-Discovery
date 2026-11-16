"""The inner loop: the model proposes and calls tools, the tools
compute and check, until the model answers."""

KEEP = ("finish", "usage", "seconds")  # recorded for every round
FIELDS = ("reasoning", "reasoning_content", "tool_calls")


def solve(client, registry, messages, max_rounds=10, seed=None):
    """Return (final text or None, transcript, rounds)."""
    tools, rounds = registry.schemas(), []
    for _ in range(max_rounds):
        reply = client.chat(messages, tools=tools, seed=seed)
        rounds.append({k: reply[k] for k in KEEP})
        msg = reply["message"]
        # Keep the reasoning behind tool calls: vLLM passes it back
        # to the model, which need not re-derive its plan.
        turn = dict(role="assistant", content=msg.get("content"))
        turn.update({k: msg[k] for k in FIELDS if msg.get(k)})
        messages.append(turn)
        calls = msg.get("tool_calls") or []
        if not calls:
            return msg.get("content") or "", messages, rounds
        for call in calls:
            fn = call["function"]
            out = registry.call(fn["name"], fn.get("arguments"))
            answer = dict(
                role="tool", tool_call_id=call["id"], content=out
            )
            messages.append(answer)
    return None, messages, rounds
