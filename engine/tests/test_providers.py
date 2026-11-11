import json
import pytest
from app import providers, settings


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("NOCODECV_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("CUSTOM_API_KEY", raising=False)


def test_gemini_chat_normalizes_text_and_tool_call(monkeypatch):
    payload = {"candidates": [{"content": {"parts": [
        {"text": "Let me look at your folders."},
        {"functionCall": {"name": "scan_folder", "args": {"path": "C:/data"}}},
    ]}}]}
    seen = {}

    def fake_post(url, **kw):
        seen["url"], seen["kw"] = url, kw
        return FakeResponse(200, payload)

    monkeypatch.setattr(providers.httpx, "post", fake_post)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    out = providers.chat_completion("gemini", "gemini-2.0-flash",
                                    [{"role": "user", "content": "hi"}],
                                    [{"type": "function", "function": {"name": "scan_folder", "description": "d",
                                                                        "parameters": {"type": "object", "properties": {}}}}])
    msg = out["choices"][0]["message"]
    assert msg["role"] == "assistant"
    assert msg["content"] == "Let me look at your folders."
    calls = msg["tool_calls"]
    assert len(calls) == 1 and calls[0]["type"] == "function"
    assert calls[0]["function"]["name"] == "scan_folder"
    assert isinstance(calls[0]["function"]["arguments"], str)
    assert json.loads(calls[0]["function"]["arguments"]) == {"path": "C:/data"}
    assert calls[0]["id"]

    # the request itself uses the documented Gemini shape
    body = seen["kw"]["json"]
    assert body["contents"][0]["role"] == "user"
    assert body["generationConfig"]["maxOutputTokens"] == 1200
    assert body["tools"][0]["functionDeclarations"][0]["name"] == "scan_folder"


def test_gemini_chat_maps_system_message_to_system_instruction(monkeypatch):
    seen = {}

    def fake_post(url, **kw):
        seen["body"] = kw["json"]
        return FakeResponse(200, {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]})

    monkeypatch.setattr(providers.httpx, "post", fake_post)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    providers.chat_completion("gemini", "gemini-2.0-flash",
                              [{"role": "system", "content": "be nice"}, {"role": "user", "content": "hi"}])
    assert seen["body"]["systemInstruction"]["parts"][0]["text"] == "be nice"


def test_openrouter_chat_is_pass_through(monkeypatch):
    payload = {"choices": [{"message": {"role": "assistant", "content": "hello"}}]}
    seen = {}

    def fake_post(url, **kw):
        seen["url"], seen["kw"] = url, kw
        return FakeResponse(200, payload)

    monkeypatch.setattr(providers.httpx, "post", fake_post)
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key")

    out = providers.chat_completion("openrouter", "openai/gpt-4o-mini", [{"role": "user", "content": "hi"}])
    assert out == payload
    assert seen["url"].endswith("/chat/completions")
    assert seen["kw"]["json"]["model"] == "openai/gpt-4o-mini"


def test_test_key_reports_bad_key(monkeypatch):
    monkeypatch.setattr(providers.httpx, "post", lambda url, **kw: FakeResponse(401, {}))
    monkeypatch.setenv("GEMINI_API_KEY", "wrong")
    res = providers.test_key("gemini")
    assert res["ok"] is False
    assert isinstance(res["message"], str) and res["message"]
    assert "401" not in res["message"]


def test_test_key_ok_on_200(monkeypatch):
    monkeypatch.setattr(providers.httpx, "post", lambda url, **kw: FakeResponse(200, {"candidates": []}))
    monkeypatch.setenv("GEMINI_API_KEY", "good")
    res = providers.test_key("gemini")
    assert res["ok"] is True and res["message"]


def test_test_key_custom_needs_base_url():
    res = providers.test_key("custom", key="x")
    assert res["ok"] is False and res["message"]


def test_estimate_cost():
    assert providers.estimate_cost("gemini", "gemini-2.0-flash", 1000, 1000) > 0
    assert providers.estimate_cost("openrouter", "openai/gpt-4o-mini", 1000, 1000) > 0
    assert providers.estimate_cost("gemini", "totally-unknown-model", 1000, 1000) == 0.0


def test_gemini_bad_key_body_maps_to_bad_key(monkeypatch):
    payload = {"error": {"code": 400, "status": "INVALID_ARGUMENT", "message": "API key not valid. Please pass a valid API key."}}
    monkeypatch.setattr(providers.httpx, "post", lambda url, **kw: FakeResponse(400, payload))
    monkeypatch.setenv("GEMINI_API_KEY", "bad")
    with pytest.raises(ValueError) as e:
        providers.chat_completion("gemini", "gemini-2.0-flash", [{"role": "user", "content": "hi"}])
    assert e.value.code == "bad_key"


def test_gemini_tool_answer_round_trip(monkeypatch):
    seen = {}

    def fake_post(url, **kw):
        seen["body"] = kw["json"]
        return FakeResponse(200, {"candidates": [{"content": {"parts": [{"text": "done"}]}}]})

    monkeypatch.setattr(providers.httpx, "post", fake_post)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    providers.chat_completion("gemini", "gemini-2.0-flash", [
        {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function",
                                                               "function": {"name": "probe_hardware", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "c1", "content": "{}"},
    ])
    contents = seen["body"]["contents"]
    assert contents[0]["role"] == "model"
    assert contents[0]["parts"][0]["functionCall"]["name"] == "probe_hardware"
    assert contents[1]["role"] == "user"
    assert contents[1]["parts"][0]["functionResponse"]["name"] == "probe_hardware"


def test_settings_roundtrip_keeps_new_keys():
    saved = settings.save({"provider": "gemini", "provider_model": "gemini-2.0-flash",
                           "custom_base_url": "http://localhost:1234/v1", "spend_cap_usd": 1.5})
    assert saved["provider"] == "gemini" and saved["custom_base_url"] == "http://localhost:1234/v1"
    loaded = settings.load()
    assert loaded["provider"] == "gemini"
    assert loaded["provider_model"] == "gemini-2.0-flash"
    assert loaded["custom_base_url"] == "http://localhost:1234/v1"
    assert loaded["spend_cap_usd"] == 1.5
    # old keys still there
    assert loaded["ai_mode"] == "own_key" and "model" in loaded and loaded["autopilot"] is False


def test_active_provider_defaults_to_gemini():
    assert settings.active_provider() == "gemini"


def test_active_provider_is_openrouter_in_proxy_mode():
    settings.save({"ai_mode": "account"})
    assert settings.active_provider() == "openrouter"


def test_list_providers_has_no_secrets(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret")
    pub = providers.list_providers()
    assert set(pub) == {"gemini", "openrouter", "custom"}
    assert pub["gemini"]["label"] == "Google Gemini"
    assert "super-secret" not in json.dumps(pub)
