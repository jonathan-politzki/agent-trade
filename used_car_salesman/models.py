"""Multi-provider model adapter.

Goal: the session loop calls `agent.step(public_message_from_other_side)`
and gets back a normalized `AgentStep` with at most one tool call. The
provider's chat history is owned by the adapter and stays in its native
format.

Provider selection is by model-string prefix:
  - claude-*     -> Anthropic
  - gpt-* / o*   -> OpenAI
  - gemini-*     -> Google (google-genai SDK)
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict


@dataclass
class AgentStep:
    text: str
    tool_call: ToolCall | None
    raw: Any = None        # provider-native response for debugging


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class AgentClient:
    """One persistent conversation with one provider/model."""

    def __init__(self, model: str, system: str, tools: list[dict], *, max_tokens: int = 1024):
        self.model = model
        self.system = system
        self.tools = tools
        self.max_tokens = max_tokens

    def step(self, user_message: str) -> AgentStep:
        raise NotImplementedError

    def report_tool_result(self, tool_call_id: str, content: str) -> None:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------

class AnthropicClient(AgentClient):
    def __init__(self, model: str, system: str, tools: list[dict], *, max_tokens: int = 1024):
        super().__init__(model, system, tools, max_tokens=max_tokens)
        from anthropic import Anthropic
        self._client = Anthropic()
        self._messages: list[dict] = []
        self._pending_user: str | None = None
        self._last_tool_use_id: str | None = None

    def _native_tools(self) -> list[dict]:
        return self.tools  # already Anthropic-native shape

    def step(self, user_message: str) -> AgentStep:
        # If the previous turn produced a tool_use but no tool_result was reported,
        # auto-ack so the API contract holds.
        if self._last_tool_use_id is not None:
            self.report_tool_result(self._last_tool_use_id, "ok")
        self._messages.append({"role": "user", "content": user_message})
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=self.system,
            tools=self._native_tools(),
            tool_choice={"type": "any"},
            messages=self._messages,
        )
        # Persist assistant content as-is.
        self._messages.append({"role": "assistant", "content": resp.content})

        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        tool_use = next((b for b in resp.content if b.type == "tool_use"), None)
        if tool_use is None:
            return AgentStep(text=text, tool_call=None, raw=resp)
        self._last_tool_use_id = tool_use.id
        return AgentStep(
            text=text,
            tool_call=ToolCall(id=tool_use.id, name=tool_use.name, args=dict(tool_use.input or {})),
            raw=resp,
        )

    def report_tool_result(self, tool_call_id: str, content: str) -> None:
        self._messages.append({
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": tool_call_id, "content": content}],
        })
        if self._last_tool_use_id == tool_call_id:
            self._last_tool_use_id = None


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------

class OpenAIClient(AgentClient):
    def __init__(self, model: str, system: str, tools: list[dict], *, max_tokens: int = 1024):
        super().__init__(model, system, tools, max_tokens=max_tokens)
        from openai import OpenAI
        self._client = OpenAI()
        self._messages: list[dict] = [{"role": "system", "content": system}]
        self._pending_tool_call_ids: list[str] = []

    def _native_tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
                },
            }
            for t in self.tools
        ]

    def step(self, user_message: str) -> AgentStep:
        # Any unresolved tool_calls from the previous assistant turn must get a result first.
        for pending_id in list(self._pending_tool_call_ids):
            self.report_tool_result(pending_id, "ok")
        self._messages.append({"role": "user", "content": user_message})

        resp = self._client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=self._messages,
            tools=self._native_tools(),
            tool_choice="required",
        )
        msg = resp.choices[0].message
        # Persist assistant turn (must include tool_calls if present).
        assistant_entry: dict = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            assistant_entry["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]
        self._messages.append(assistant_entry)

        if not msg.tool_calls:
            return AgentStep(text=msg.content or "", tool_call=None, raw=resp)

        # Take only the first tool call (we want one action per turn).
        tc = msg.tool_calls[0]
        # All tool_calls produced must be reported back (even those we ignore).
        self._pending_tool_call_ids = [t.id for t in msg.tool_calls]
        try:
            args = json.loads(tc.function.arguments or "{}")
        except json.JSONDecodeError:
            args = {}
        return AgentStep(
            text=msg.content or "",
            tool_call=ToolCall(id=tc.id, name=tc.function.name, args=args),
            raw=resp,
        )

    def report_tool_result(self, tool_call_id: str, content: str) -> None:
        self._messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": content})
        if tool_call_id in self._pending_tool_call_ids:
            self._pending_tool_call_ids.remove(tool_call_id)


# ---------------------------------------------------------------------------
# Gemini (google-genai SDK)
# ---------------------------------------------------------------------------

def _sanitize_schema_for_gemini(schema: dict) -> dict:
    """Gemini accepts an OpenAPI-ish schema but is strict about extra keys.
    Strip unsupported fields and keep only what it likes.
    """
    if not isinstance(schema, dict):
        return schema
    allowed = {"type", "properties", "required", "items", "description", "enum", "format"}
    out: dict = {}
    for k, v in schema.items():
        if k not in allowed:
            continue
        if k == "properties" and isinstance(v, dict):
            out["properties"] = {pk: _sanitize_schema_for_gemini(pv) for pk, pv in v.items()}
        elif k == "items" and isinstance(v, dict):
            out["items"] = _sanitize_schema_for_gemini(v)
        else:
            out[k] = v
    # Gemini wants type uppercase (string -> STRING).
    if "type" in out and isinstance(out["type"], str):
        out["type"] = out["type"].upper()
    return out


class GeminiClient(AgentClient):
    def __init__(self, model: str, system: str, tools: list[dict], *, max_tokens: int = 1024):
        super().__init__(model, system, tools, max_tokens=max_tokens)
        from google import genai
        from google.genai import types as gt
        self._genai = genai
        self._gt = gt

        # Vertex mode if either env is set or GOOGLE_GENAI_USE_VERTEXAI=true.
        use_vertex = (
            os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in ("1", "true", "yes")
            or bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))
        )

        if use_vertex:
            project = os.environ.get("GOOGLE_CLOUD_PROJECT")
            location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
            if not project:
                raise RuntimeError(
                    "Vertex mode requested but GOOGLE_CLOUD_PROJECT is not set."
                )
            # Auth comes from ADC (gcloud auth application-default login,
            # or gcloud config's active service account).
            self._client = genai.Client(vertexai=True, project=project, location=location)
        else:
            api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "Need either Vertex env (GOOGLE_CLOUD_PROJECT) or "
                    "GEMINI_API_KEY / GOOGLE_API_KEY for direct-API mode."
                )
            self._client = genai.Client(api_key=api_key)

        self._contents: list[Any] = []
        self._last_call_name: str | None = None
        self._last_call_id: str | None = None

    def _native_tools(self):
        gt = self._gt
        decls = [
            {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": _sanitize_schema_for_gemini(t.get("input_schema", {"type": "object", "properties": {}})),
            }
            for t in self.tools
        ]
        return [gt.Tool(function_declarations=decls)]

    def _config(self):
        gt = self._gt
        return gt.GenerateContentConfig(
            system_instruction=self.system,
            tools=self._native_tools(),
            tool_config=gt.ToolConfig(
                function_calling_config=gt.FunctionCallingConfig(mode="ANY")
            ),
            max_output_tokens=self.max_tokens,
        )

    def step(self, user_message: str) -> AgentStep:
        gt = self._gt
        # If previous turn produced a function call but no response was reported, auto-ack.
        if self._last_call_id is not None and self._last_call_name is not None:
            self.report_tool_result(self._last_call_id, "ok")

        self._contents.append(gt.Content(role="user", parts=[gt.Part.from_text(text=user_message)]))
        resp = self._client.models.generate_content(
            model=self.model,
            config=self._config(),
            contents=self._contents,
        )

        # Find the first function call in the response.
        text_out = ""
        tool_call: ToolCall | None = None
        try:
            parts = resp.candidates[0].content.parts or []
        except Exception:
            parts = []
        model_parts = []
        for p in parts:
            model_parts.append(p)
            if getattr(p, "text", None):
                text_out += p.text
            fc = getattr(p, "function_call", None)
            if fc is not None and tool_call is None:
                # google-genai's function_call has .name and .args (a Struct/dict).
                args = dict(fc.args) if fc.args else {}
                # Use a deterministic id (Gemini doesn't supply one).
                call_id = f"gemini_{uuid.uuid4().hex[:12]}"
                tool_call = ToolCall(id=call_id, name=fc.name, args=args)

        # Persist the model turn verbatim.
        if model_parts:
            self._contents.append(gt.Content(role="model", parts=model_parts))

        if tool_call is not None:
            self._last_call_name = tool_call.name
            self._last_call_id = tool_call.id

        return AgentStep(text=text_out.strip(), tool_call=tool_call, raw=resp)

    def report_tool_result(self, tool_call_id: str, content: str) -> None:
        gt = self._gt
        if self._last_call_name is None:
            return
        fn_name = self._last_call_name
        # Gemini wants function_response to carry the same function name.
        self._contents.append(gt.Content(
            role="user",
            parts=[gt.Part.from_function_response(name=fn_name, response={"result": content})],
        ))
        if self._last_call_id == tool_call_id:
            self._last_call_id = None
            self._last_call_name = None


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def make_agent(model: str, system: str, tools: list[dict], *, max_tokens: int = 1024) -> AgentClient:
    m = model.lower()
    if m.startswith("claude"):
        return AnthropicClient(model, system, tools, max_tokens=max_tokens)
    if m.startswith("gpt") or m.startswith("o1") or m.startswith("o3") or m.startswith("o4") or m.startswith("chatgpt"):
        return OpenAIClient(model, system, tools, max_tokens=max_tokens)
    if m.startswith("gemini"):
        return GeminiClient(model, system, tools, max_tokens=max_tokens)
    raise ValueError(f"Unknown model: {model}. Expected prefix claude-, gpt-, o*, or gemini-.")
