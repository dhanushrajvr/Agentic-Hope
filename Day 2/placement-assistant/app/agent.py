import time  # noqa: F401  (you will time each tool call)
from collections.abc import Callable

from app.memory import ConversationStore
from app.providers import AgentError  # noqa: F401
from app.tools.placement_tools import PlacementTools

MAX_STEPS = 8

SYSTEM = """You are the Placement Assistant for an engineering college's placement cell.
You are talking to the student with roll number {student_id}. Act only for this student.
Use the tools for every fact about drives, eligibility, applications and slots; never guess.
Eligibility is decided by check_eligibility, not by you. Keep replies short and concrete."""


class Agent:
    """A small agent: one student, one conversation, the placement tools."""

    def __init__(self, provider, tools: PlacementTools, student_id: str,
                 memory: ConversationStore | None = None, thread_id: str | None = None,
                 on_step: Callable[[dict], None] | None = None):
        self.provider = provider
        self.tools = tools
        self.system = SYSTEM.format(student_id=student_id)
        self.memory = memory
        self.thread_id = thread_id
        self.on_step = on_step
        self.contents: list[dict] = []     # what the model sees, turn after turn
        self.trace: list[dict] = []        # what happened, step by step
        # TODO (Part 3.3): if memory and thread_id are given, start self.contents from
        # memory.load_history(thread_id), as {"role": ..., "text": ...} entries.

    def _log(self, entry: dict) -> None:
        """Add one entry to the trace and tell on_step about it. (Given.)"""
        self.trace.append(entry)
        if self.on_step:
            self.on_step(entry)

    # ------------------------------------------------------------------ Part 2.1

    def run_tool(self, name: str, args: dict) -> dict:
        """Call a tool without letting the agent crash.

        Args:
            name: tool name
            args: arguments to pass to the tool

        Returns:
            Either the tool's normal result, or a safe error dict the model can recover from.
        """
        try:
            result = self.tools.call(name, args)
            return result
        except NotImplementedError as e:
            return {"error": "not_implemented", "hint": type(e).__name__}
        except Exception as e:
            return {"error": "tool_failed", "hint": type(e).__name__}

    # ------------------------------------------------------------------ Part 2.2

    '''
    def ask(self, text: str) -> str:
        """One user turn: loop model calls and tool calls until the model answers.

        TODO (Part 2.2):
          1. Append {"role": "user", "text": text} to self.contents.
          2. Call self.provider.generate(self.system, self.contents, list(self.tools.functions().values())).
             Log {"step", "kind": "model", "tokens_in", "tokens_out"}.
          3. No tool calls? Append {"role": "model", "text": reply, "raw": turn.raw} and return the reply.
          4. Otherwise append {"role": "model", "text": turn.text, "raw": turn.raw,
             "tool_calls": [{"name", "args"}, ...]}, then for EACH call, in order:
             run_tool, log {"step", "kind": "tool", "tool", "args", "result", "ok", "ms"}
             (ok means "error" not in result), and append {"role": "tool", "name", "result"}.
          5. Go back to 2. Steps are numbered 1, 2, 3... across model and tool steps.
          6. After MAX_STEPS steps without an answer, raise AgentError("step_limit", ...).

        TODO (Part 3.3), when self.memory is set: save the user message and start a run before
        the loop; record every model step and tool call as it happens; save the reply and finish
        the run as succeeded; on AgentError, finish the run as failed with e.code and re-raise.
        """
        raise NotImplementedError 
    
    '''

    
    def ask(self, text: str) -> str:
        """One user turn: loop model calls and tool calls until the model answers."""
        self.contents.append({"role": "user", "text": text})

        step = 1
        while True:
            if step > MAX_STEPS:
                raise AgentError("step_limit", "Maximum tool/model steps exceeded.")

            turn = self.provider.generate(
                self.system,
                self.contents,
                list(self.tools.functions().values()),
            )

            self._log({
                "step": step,
                "kind": "model",
                "tokens_in": turn.tokens_in,
                "tokens_out": turn.tokens_out,
            })
            step += 1

            if not turn.tool_calls:
                reply = turn.text
                self.contents.append({
                    "role": "model",
                    "text": reply,
                    "raw": turn.raw,
                })
                return reply

            self.contents.append({
                "role": "model",
                "text": turn.text,
                "raw": turn.raw,
                "tool_calls": [
                    {"name": c.name, "args": c.args}
                    for c in turn.tool_calls
                ],
            })

            for call in turn.tool_calls:
                started = time.perf_counter()
                result = self.run_tool(call.name, call.args)
                latency_ms = int((time.perf_counter() - started) * 1000)

                ok = "error" not in result
                self._log({
                    "step": step,
                    "kind": "tool",
                    "tool": call.name,
                    "args": call.args,
                    "result": result,
                    "ok": ok,
                    "ms": latency_ms,
                })
                step += 1

                self.contents.append({
                    "role": "tool",
                    "name": call.name,
                    "result": result,
                })
