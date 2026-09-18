from collections.abc import Callable

from pydantic import BaseModel, Field, ValidationError, model_validator  # noqa: F401


class FailedRule(BaseModel):
    rule_id: int
    rule: str
    actual: str | float


class EligibilityVerdict(BaseModel):
    student_id: str = Field(pattern=r"^\d{2}[A-Z]{2}\d{3}$")
    drive_id: int
    eligible: bool
    failed_rules: list[FailedRule]
    summary: str = Field(min_length=1, max_length=280)

    # TODO (stretch): add a model_validator(mode="after") that rejects a verdict whose
    # `eligible` flag contradicts `failed_rules`. The error message must contain "contradicts".
    @model_validator(mode="after")
    def check_consistency(self) -> "EligibilityVerdict":
        # If there are failed rules, eligible must be False; if no failed rules, eligible must be True.
        if self.failed_rules and self.eligible:
            raise ValueError("eligible True contradicts failed_rules")
        if not self.failed_rules and not self.eligible:
            raise ValueError("eligible False contradicts failed_rules")
        return self

class VerdictInvalid(Exception):
    def __init__(self, attempts: int, last_errors: list):
        super().__init__(f"no valid verdict after {attempts} attempts")
        self.attempts = attempts
        self.last_errors = last_errors


Generate = Callable[[list[str]], str]


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
        t = t.rsplit("```", 1)[0]
    return t.strip()


def structured_verdict(generate: Generate, prompt: str, max_retries: int = 2) -> EligibilityVerdict:
    """Ask the model for an EligibilityVerdict; feed validation errors back; give up after max_retries.

    Behavior:
      - call `generate(messages)` where `messages` is a list of strings starting at `[prompt]`
      - try to parse with `EligibilityVerdict.model_validate_json(_strip_fences(raw))`
      - on `ValidationError` append the raw reply and a feedback message containing
        "failed validation" + the validation messages, then try again
      - allow at most `1 + max_retries` calls, then raise `VerdictInvalid(attempts, last_errors)`
    """
    messages: list[str] = [prompt]
    attempts = 0
    last_errors = []
    while attempts <= max_retries:
        raw = generate(messages)
        attempts += 1
        try:
            cleaned = _strip_fences(raw)
            verdict = EligibilityVerdict.model_validate_json(cleaned)
            return verdict
        except ValidationError as e:
            last_errors = [err.get("msg", str(err)) for err in e.errors()]
            # append the model reply and a human-readable feedback message, then retry
            messages.append(raw)
            feedback = "failed validation: " + "; ".join(last_errors)
            messages.append(feedback)
            # continue loop to retry
    # exhausted retries
    raise VerdictInvalid(attempts, last_errors)
