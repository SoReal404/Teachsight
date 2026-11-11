"""AI providers. One place that talks to Google Gemini, OpenRouter or any OpenAI-compatible endpoint.

Keys never live in settings.json and are never logged: they come from an environment variable first,
then from the Windows keychain (service "NoCodeCV").
"""
from __future__ import annotations
import json, os
import httpx

KEYRING_SERVICE = "NoCodeCV"

PROVIDERS = {
    "gemini": {
        "label": "Google Gemini",
        "default_model": "gemini-2.0-flash",
        "env": "GEMINI_API_KEY",
        "keyring_user": "gemini_api_key",
        "key_placeholder": "AIza...",
        "key_help": "Get a free key at https://aistudio.google.com/apikey",
        "free_tier": True,
    },
    "openrouter": {
        "label": "OpenRouter",
        "default_model": "openai/gpt-4o-mini",
        "env": "OPENROUTER_API_KEY",
        "keyring_user": "openrouter_api_key",
        "key_placeholder": "sk-or-...",
        "key_help": "Get a key at https://openrouter.ai/keys",
        "free_tier": False,
    },
    "custom": {
        "label": "Other (OpenAI-compatible)",
        "default_model": "",
        "env": "CUSTOM_API_KEY",
        "keyring_user": "custom_api_key",
        "key_placeholder": "your key",
        "key_help": "Any endpoint that speaks the OpenAI chat-completions format.",
        "free_tier": False,
    },
}

# Public base URLs. The "custom" provider always comes from settings.
BASES = {
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
    "openrouter": "https://openrouter.ai/api/v1",
}

# Rough USD price per 1M tokens: model -> (prompt, completion)
PRICE = {
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-1.5-flash": (0.075, 0.30),
    "gpt-4o-mini": (0.15, 0.60),
}


class ProviderError(ValueError):
    """A provider call failed. `code` is one of no_key/bad_key/no_credit/rate/network/provider."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


# ---- keys ----

def list_providers() -> dict:
    """Public info per provider. No key values, ever."""
    out = {}
    for pid, p in PROVIDERS.items():
        out[pid] = {
            "label": p["label"],
            "default_model": p["default_model"],
            "env": p["env"],
            "key_placeholder": p["key_placeholder"],
            "key_help": p["key_help"],
            "free_tier": p["free_tier"],
            "has_key": bool(get_key(pid)),
        }
    return out


def get_key(provider: str) -> str | None:
    """The key for a provider: environment variable first, then the Windows keychain."""
    p = PROVIDERS.get(provider)
    if not p:
        return None
    v = os.environ.get(p["env"])
    if v:
        return v.strip() or None
    try:
        import keyring
        v = keyring.get_password(KEYRING_SERVICE, p["keyring_user"])
    except Exception:
        return None
    return v.strip() if v and v.strip() else None


def set_key(provider: str, key: str) -> None:
    """Store the key for a provider in the Windows keychain."""
    p = PROVIDERS.get(provider)
    if not p:
        raise ValueError("Unknown AI provider.")
    import keyring
    keyring.set_password(KEYRING_SERVICE, p["keyring_user"], (key or "").strip())


def delete_key(provider: str) -> None:
    """Remove the stored key for a provider. Never raises."""
    p = PROVIDERS.get(provider)
    if not p:
        return
    try:
        import keyring
        keyring.delete_password(KEYRING_SERVICE, p["keyring_user"])
    except Exception:
        pass


# ---- helpers ----

def _label(provider: str) -> str:
    return (PROVIDERS.get(provider) or {}).get("label", "The AI service")


def _base_url(provider: str, base_url: str | None) -> str:
    if base_url:
        return base_url.rstrip("/")
    if provider == "custom":
        raise ProviderError("provider", "Add the address of your AI server in Settings.")
    return BASES.get(provider, "").rstrip("/")


def _need_key(provider: str, key: str | None) -> str:
    key = (key or "").strip() or get_key(provider)
    if not key:
        raise ProviderError("no_key", f"Add your {_label(provider)} key in Settings so I can chat.")
    return key


def _is_bad_key_body(r) -> bool:
    """Some services (Gemini) report a bad key with 400 plus an API_KEY_INVALID style message."""
    try:
        body = json.dumps(r.json())
    except Exception:
        return False
    body = body.upper()
    return "API_KEY_INVALID" in body or "INVALID API KEY" in body or "API KEY NOT VALID" in body


def _check_status(r) -> None:
    """Turn an HTTP status into a plain-language ProviderError."""
    code = getattr(r, "status_code", 0)
    if code in (401, 403):
        raise ProviderError("bad_key", "The AI service did not accept the key. Check it in Settings.")
    if code == 402:
        raise ProviderError("no_credit", "You are out of AI credits.")
    if code == 429:
        raise ProviderError("rate", "The AI service is busy. Try again in a moment.")
    if code == 400 and _is_bad_key_body(r):
        raise ProviderError("bad_key", "The AI service did not accept the key. Check it in Settings.")
    if code != 200:
        raise ProviderError("provider", f"The AI service returned an error ({code}).")


def _post(url: str, timeout: int = 90, **kw):
    try:
        return httpx.post(url, timeout=timeout, **kw)
    except httpx.HTTPError:
        raise ProviderError("network", "I can't reach the AI service. Check your internet connection.")


def _gemini_tools(tools: list | None) -> list | None:
    """OpenAI-style tool schemas map 1:1 onto Gemini functionDeclarations."""
    if not tools:
        return None
    decls = []
    for t in tools:
        fn = (t or {}).get("function") or {}
        decl = {"name": fn.get("name", "")}
        if fn.get("description"):
            decl["description"] = fn["description"]
        if fn.get("parameters"):
            decl["parameters"] = fn["parameters"]
        decls.append(decl)
    return [{"functionDeclarations": decls}] if decls else None


def _gemini_contents(messages: list[dict]) -> tuple[list, str]:
    """Split a chat into Gemini contents + the system instruction."""
    contents, system, names = [], [], {}
    for m in messages or []:
        role = m.get("role")
        if role == "system":
            system.append(str(m.get("content") or ""))
        elif role == "assistant":
            parts = []
            if m.get("content"):
                parts.append({"text": str(m["content"])})
            for tc in (m.get("tool_calls") or []):
                fn = (tc or {}).get("function") or {}
                name = fn.get("name", "")
                if tc.get("id"):
                    names[tc["id"]] = name
                raw = fn.get("arguments")
                if isinstance(raw, str):
                    try:
                        args = json.loads(raw) if raw.strip() else {}
                    except json.JSONDecodeError:
                        args = {}
                else:
                    args = raw or {}
                parts.append({"functionCall": {"name": name, "args": args}})
            if parts:
                contents.append({"role": "model", "parts": parts})
        elif role == "tool":
            name = names.get(m.get("tool_call_id")) or "tool"
            contents.append({"role": "user", "parts": [{"functionResponse": {"name": name, "response": {"result": m.get("content") or ""}}}]})
        else:
            contents.append({"role": "user", "parts": [{"text": str(m.get("content") or "")}]})
    return contents, "\n\n".join(x for x in system if x)


def _gemini_reply(data: dict) -> dict:
    """Normalize a Gemini generateContent answer to the OpenAI-ish shape the agent expects."""
    candidates = data.get("candidates") or []
    texts, calls = [], []
    if candidates:
        parts = ((candidates[0] or {}).get("content") or {}).get("parts") or []
        for part in parts:
            if not isinstance(part, dict):
                continue
            fc = part.get("functionCall")
            if fc:
                args = fc.get("args")
                arguments = args if isinstance(args, str) else json.dumps(args or {}, ensure_ascii=False)
                name = fc.get("name", "")
                calls.append({"id": f"call_{len(calls)}_{name}", "type": "function",
                              "function": {"name": name, "arguments": arguments}})
            elif "text" in part:
                texts.append(str(part.get("text") or ""))
    content = "\n".join(t for t in texts if t).strip() or None
    return {"choices": [{"message": {"role": "assistant", "content": content, "tool_calls": calls}}]}


# ---- chat ----

def chat_completion(provider: str, model: str, messages: list[dict], tools: list | None = None,
                    base_url: str | None = None) -> dict:
    """Chat with any provider. Returns the OpenAI-ish shape: {"choices":[{"message":{...}}]}."""
    if provider == "gemini":
        return _gemini_chat(model, messages, tools, base_url)
    return _openai_chat(provider, model, messages, tools, base_url)


def _gemini_chat(model: str, messages: list[dict], tools: list | None, base_url: str | None) -> dict:
    key = _need_key("gemini", None)
    if not model:
        raise ProviderError("provider", "Choose which Gemini model to use in Settings.")
    base = _base_url("gemini", base_url)
    contents, system = _gemini_contents(messages)
    body = {"contents": contents,
            "generationConfig": {"maxOutputTokens": 1200, "temperature": 0.2}}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    gtools = _gemini_tools(tools)
    if gtools:
        body["tools"] = gtools
    url = f"{base}/models/{model}:generateContent"
    r = _post(url, params={"key": key}, json=body)
    _check_status(r)
    return _gemini_reply(r.json())


def _openai_chat(provider: str, model: str, messages: list[dict], tools: list | None, base_url: str | None) -> dict:
    key = _need_key(provider, None)
    base = _base_url(provider, base_url)
    if not model:
        raise ProviderError("provider", "Choose which model to use in Settings.")
    body = {"model": model, "messages": messages, "max_tokens": 1200}
    if tools:
        body["tools"] = tools
    headers = {"Authorization": f"Bearer {key}"}
    if provider == "openrouter":
        headers.update({"HTTP-Referer": "https://nocodecv.app", "X-Title": "NoCode CV"})
    r = _post(f"{base}/chat/completions", headers=headers, json=body)
    _check_status(r)
    return r.json()


# ---- key test ----

def test_key(provider: str, key: str | None = None, base_url: str | None = None, model: str | None = None) -> dict:
    """Check a provider key with one tiny real call. Always returns {"ok": bool, "message": str}."""
    label = _label(provider)
    if provider == "custom" and not (base_url or "").strip():
        return {"ok": False, "message": "Add the address of your AI server in Settings first."}
    try:
        key = (key or "").strip() or get_key(provider)
    except Exception:
        key = None
    if not key:
        return {"ok": False, "message": f"Add your {label} key in Settings first."}
    try:
        if provider == "gemini":
            m = model or PROVIDERS["gemini"]["default_model"]
            base = _base_url("gemini", base_url)
            body = {"contents": [{"role": "user", "parts": [{"text": "Hi"}]}],
                    "generationConfig": {"maxOutputTokens": 8, "temperature": 0.2}}
            r = _post(f"{base}/models/{m}:generateContent", params={"key": key}, json=body, timeout=30)
        else:
            m = model or PROVIDERS.get(provider, {}).get("default_model") or "gpt-4o-mini"
            base = _base_url(provider, base_url)
            headers = {"Authorization": f"Bearer {key}"}
            if provider == "openrouter":
                headers.update({"HTTP-Referer": "https://nocodecv.app", "X-Title": "NoCode CV"})
            body = {"model": m, "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 8}
            r = _post(f"{base}/chat/completions", headers=headers, json=body, timeout=30)
    except ProviderError as e:
        return {"ok": False, "message": e.message}
    except Exception:
        return {"ok": False, "message": "I can't reach the AI service. Check your internet connection."}
    code = getattr(r, "status_code", 0)
    if code in (401, 403):
        return {"ok": False, "message": f"{label} did not accept that key. Check it and try again."}
    if code == 402:
        return {"ok": False, "message": "This key has no credits left."}
    if code == 429:
        return {"ok": False, "message": f"{label} is busy right now. Try again in a moment."}
    if code != 200:
        return {"ok": False, "message": f"{label} returned an error ({code}). Check the key and the model name."}
    return {"ok": True, "message": f"{label} is ready to use."}


# ---- money ----

def estimate_cost(provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Rough USD cost of a call. Unknown model -> 0.0."""
    if not model:
        return 0.0
    for name, (pin, pout) in PRICE.items():
        if model == name or model.endswith("/" + name):
            return (max(0, prompt_tokens) / 1_000_000) * pin + (max(0, completion_tokens) / 1_000_000) * pout
    return 0.0
