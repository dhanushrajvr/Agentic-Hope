# Part 3 — memory design notes

1) Entities discovered in the Day 1 ConversationStore
- **thread**: conversation container / unit tying messages to a student (already present).
- **message**: a single exchanged text (one user or one model utterance). Identified by (thread_id, seq).
- **run**: a recorded agent execution (a model invocation or an agent turn that may include tool usage, error state, token counts, runtime metadata).
- **run_step**: a step inside a run (ordered seq) that is either a `model` step or a `tool` step.
- **tool_call**: the concrete invocation of an external tool (arguments, result, success flag, latency) produced during a `tool` run_step.

2) What is a run, and why is it not a message?
- **Message**: external communication (user → agent, or model → user). Short-lived conversational units visible in the UI.
- **Run**: internal unit of work capturing how the agent processed an input (model used, tokens consumed/produced, start/finish times, success/failure, error codes). A single run may correspond to one model invocation or to an agent decision sequence; it is about "what the agent did" rather than "what was said". Storing runs lets us measure cost, debug failures, and relate tool usage to a single agent decision.

3) Why is tool_call one-to-one with run_step?
- Each `run_step` represents a single logical action in the run (either a model action or a tool action). When the agent executes a tool action, it performs exactly one tool call at that step. Modeling tool calls as a 1:1 sub-record keeps the data schema simple (one call per tool step), enforces clarity about causality, and makes metrics (ok, latency, args/result) directly attributable to a specific run step.

4) Why keep the agent's memory separate from placement data?
- **Separation of concerns**: agent memory records interaction and execution metadata; placement data (students, drives, applications) is domain/business data with different schema, access rules, and lifecycle.
- **Privacy & security**: memory may contain transient user text, system traces, or model errors that should have different retention/visibility rules.
- **Migration & size**: memory growth patterns and pruning policy differ from core domain data; mixing them complicates backups and migrations.
- **Correctness**: mixing increases risk of accidental denormalization and application-level coupling (e.g., deleting a student could inadvertently erase conversation history or vice-versa).
- Keep the agent memory as an independent, auditable store that references domain rows (via IDs) only when needed.