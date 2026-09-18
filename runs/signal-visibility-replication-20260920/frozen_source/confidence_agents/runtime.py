"""Small OpenRouter adapter, durable per-call records, and a deterministic mock."""
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from .design import digest, parse, rng

BASE = "https://openrouter.ai/api/v1"


def output_format(initial):
    properties = {"answer": {"type": "string", "enum": ["A", "B"]}}
    if initial:
        properties.update(reason={"type": "string"}, p_B={"type": "number", "minimum": 0, "maximum": 1})
    return {"type": "json_schema", "json_schema": {"name": "initial_answer" if initial else "updated_answer",
            "strict": True, "schema": {"type": "object", "properties": properties,
                                       "required": list(properties), "additionalProperties": False}}}


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    for attempt in range(4):
        try:
            temporary.replace(path)
            break
        except PermissionError:
            if attempt == 3:
                raise
            time.sleep(.1 * (attempt + 1))


def catalog(models):
    with urllib.request.urlopen(BASE + "/models", timeout=30) as response:
        entries = {m["id"]: m for m in json.load(response)["data"]}
    selected = {}
    for key, model in models.items():
        if model["id"] not in entries:
            raise ValueError(f"Unavailable exact model ID: {model['id']}; no substitution permitted")
        entry = entries[model["id"]]
        if model.get("structured_outputs") and not {"response_format", "structured_outputs"} <= set(entry.get("supported_parameters", [])):
            raise ValueError(f"Cannot verify strict structured outputs for {model['id']}")
        effort = model.get("reasoning_effort")
        if effort is not None:
            supported = entry.get("reasoning", {}).get("supported_efforts", [])
            if effort not in supported:
                raise ValueError(f"Cannot verify reasoning effort {effort} for {model['id']}")
        selected[key] = entry
    return selected


class Calls:
    def __init__(self, directory, backend, max_requests, max_tokens):
        self.directory = Path(directory) / "calls"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.backend, self.limit, self.max_tokens = backend, max_requests, max_tokens
        self.count = len(list(self.directory.glob("*.json")))
        self.key = os.environ.get("OPENROUTER_API_KEY") if backend == "openrouter" else None
        if backend == "openrouter" and not self.key:
            raise ValueError("Set OPENROUTER_API_KEY in the environment before a live run")

    def ask(self, call_id, model, messages, initial=False):
        body = {"model": model["id"], "messages": messages, "max_tokens": self.max_tokens,
                "provider": {"allow_fallbacks": False, "require_parameters": True}}
        if model.get("provider"):
            body["provider"]["only"] = [model["provider"]]
        if "reasoning_effort" in model:
            body["reasoning"] = {"effort": model["reasoning_effort"]}
        if model.get("structured_outputs"):
            body["response_format"] = output_format(initial)
        signature = digest(body)
        path = self.directory / (digest(call_id) + ".json")
        if path.exists():
            record = json.loads(path.read_text(encoding="utf-8"))
            if record["request_hash"] != signature:
                raise ValueError("Resume request differs from saved request")
            if record["status"] != "complete":
                raise RuntimeError(f"Unresolved request {call_id}. Inspect its call record; do not blindly retry.")
            return record["parsed"]
        if self.count >= self.limit:
            raise RuntimeError("Request cap reached; increase max_requests via CLI to resume")
        self.count += 1
        record = {"call_id": call_id, "request_hash": signature, "request": body,
                  "backend": self.backend, "status": "pending", "started_at": time.time()}
        # Save before sending. A timeout/crash may still incur a charge: never automatically resend.
        save(path, record)
        start = time.monotonic()
        try:
            if self.backend == "mock":
                r = rng(call_id, signature)
                answer = r.choice(["A", "B"])
                obj = {"answer": answer}
                if initial:
                    obj.update(reason="Synthetic mock response; not model evidence.", p_B=.7 if answer == "B" else .3)
                response = {"model": model["id"], "provider": "mock", "choices": [
                    {"message": {"content": json.dumps(obj)}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0}}
            else:
                request = urllib.request.Request(BASE + "/chat/completions",
                    data=json.dumps(body).encode(), headers={"Content-Type": "application/json",
                        "Authorization": "Bearer " + self.key,
                        "X-OpenRouter-Title": "confidence-agents-pilot"})
                with urllib.request.urlopen(request, timeout=120) as stream:
                    response = json.load(stream)
                if "error" in response:
                    raise RuntimeError("Provider returned an error response")
            choice = response["choices"][0]
            content = choice["message"].get("content")
            parsed = parse(content, initial) if choice.get("finish_reason") == "stop" else None
            failure = None
            if choice.get("finish_reason") == "length":
                failure = "output_token_limit"
            elif choice["message"].get("refusal"):
                failure = "refusal"
            elif choice.get("finish_reason") != "stop":
                failure = "non_stop_finish"
            elif parsed is None:
                failure = "invalid_answer_format"
            record.update(status="complete", response=response, parsed=parsed,
                          valid=parsed is not None, failure_category=failure,
                          elapsed_seconds=time.monotonic()-start)
            save(path, record)
            return parsed
        except Exception as exc:
            # Exception bodies/headers may contain credentials or provider internals: don't log them.
            record.update(status="unresolved", error_type=type(exc).__name__,
                          http_status=getattr(exc, "code", None), elapsed_seconds=time.monotonic()-start)
            if isinstance(exc, urllib.error.HTTPError):
                try:
                    error = json.loads(exc.read(16384)).get("error", {})
                    message = error.get("message") if isinstance(error, dict) else None
                    if isinstance(message, str):
                        record["error_message"] = message.replace(self.key or "\x00", "[REDACTED]")[:2000]
                except (ValueError, OSError):
                    pass
            try:
                save(path, record)
            except OSError:
                raise RuntimeError(f"Request {call_id} failed ({type(exc).__name__}, HTTP {record['http_status']}); "
                                   "saving its record also failed; inspect the .json.tmp file") from None
            detail = record.get("error_message", type(exc).__name__)
            raise RuntimeError(f"Request {call_id} failed (HTTP {record['http_status']}): {detail}; inspect saved record") from None
