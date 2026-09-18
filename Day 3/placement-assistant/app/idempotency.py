"""Stable fingerprints for side effects. Hashing, used for exactly-once."""
import hashlib  # noqa: F401
import json  # noqa: F401
import uuid
from datetime import date


def canonical_json(value) -> str:
    """Normalize any JSON-like value into a stable, canonical string representation.

    This method ensures that semantically identical values serialize to the same bytes by sorting dict
    keys, compacting JSON output without spaces, and converting integer-like floats such as 12.0 to 12.
    The normalization is recursive, so nested dictionaries and lists are handled consistently as well.

    Args:
        value: Any value that can be serialized as JSON, including nested dicts and lists.

    Returns:
        A canonical JSON string that is stable for equivalent values.
    """
    def normalize(v):
        if isinstance(v, float):
            if v.is_integer():
                return int(v)
            return v
        if isinstance(v, dict):
            return {str(k): normalize(v[k]) for k in sorted(v, key=str)}
        if isinstance(v, list):
            return [normalize(item) for item in v]
        if isinstance(v, tuple):
            return [normalize(item) for item in v]
        return v

    return json.dumps(normalize(value), separators=(",", ":"), sort_keys=True)


def idempotency_key(run_id: str, step_seq: int, tool_name: str, args: dict) -> str:
    """Return a deterministic SHA-256 fingerprint for a tool call on one run step.

    The same logical tool call on the same step of the same run must always produce the same key,
    even if argument ordering or equivalent numeric representations differ. The key is computed from a
    canonical JSON encoding of the full call tuple.

    Args:
        run_id: The run this call belongs to.
        step_seq: The sequential step number within the run.
        tool_name: The tool being invoked.
        args: The tool call arguments.

    Returns:
        A 64-character hexadecimal SHA-256 digest.
    """
    return hashlib.sha256(canonical_json([run_id, step_seq, tool_name, args]).encode()).hexdigest()


def notification_dedupe_key(roll_no: str, message: str, day: date) -> str:
    """Build a stable dedupe key for a notification sent to one student on one day.

    The message is normalized by trimming surrounding whitespace and collapsing runs of whitespace to a
    single space before hashing. The resulting value is combined with the student's roll number and the
    ISO date so the same message sent on the same day gets the same key, while a different day or
    different student produces a different key.

    Args:
        roll_no: The student roll number receiving the message.
        message: The notification text to normalize and hash.
        day: The date the notification is being sent.

    Returns:
        A 64-character SHA-256 hex digest for the dedupe key.
    """
    normalized = " ".join(message.strip().split())
    return hashlib.sha256(canonical_json([roll_no, normalized, day.isoformat()]).encode()).hexdigest()
