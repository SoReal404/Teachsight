"""App settings and the OpenRouter key. The key never goes in settings.json: env var, .env file, or the OS keychain."""
from __future__ import annotations
import json, os
from pathlib import Path

DEFAULTS = {
    "ai_mode": "own_key",          # own_key = your own provider key on this PC (dev / power users); account = our proxy server (paid plans)
    "model": os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini"),   # change in Settings; see openrouter.ai/models
    "provider": "gemini",          # gemini | openrouter | custom (see app/providers.py)
    "provider_model": "",          # model for the active provider; empty = provider default
    "custom_base_url": "",         # base URL for the custom (OpenAI-compatible) provider
    "spend_cap_usd": 0.0,          # optional soft cap; 0 = no cap
    "proxy_url": "",               # used when ai_mode == account
    "license_key": "",             # used when ai_mode == account
    "send_thumbnails": False,      # reserved for vision features; images are never sent today
    "autopilot": False,            # always pick the recommended fix without asking (not for severe problems)
    "notifications": True,
}
KEYRING_SERVICE, KEYRING_USER = "NoCodeCV", "openrouter_api_key"


def app_dir() -> Path:
    base = os.environ.get("NOCODECV_HOME") or (Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "NoCodeCV")
    p = Path(base); p.mkdir(parents=True, exist_ok=True)
    return p


def _load_dotenv():
    f = Path(__file__).resolve().parent.parent / ".env"
    if f.is_file():
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()


def load() -> dict:
    f = app_dir() / "settings.json"
    data = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
    return {**DEFAULTS, **data}


def save(patch: dict) -> dict:
    s = load()
    s.update({k: v for k, v in patch.items() if k in DEFAULTS and v is not None})
    (app_dir() / "settings.json").write_text(json.dumps(s, indent=2), encoding="utf-8")
    return s


def active_provider() -> str:
    """Which provider the AI should use. Proxy mode always goes through OpenRouter."""
    s = load()
    if s.get("ai_mode") == "account":
        return "openrouter"
    return s.get("provider") or DEFAULTS["provider"]


def get_api_key() -> str | None:
    """The OpenRouter key (kept for the existing /settings/api-key route)."""
    if os.environ.get("OPENROUTER_API_KEY"):
        return os.environ["OPENROUTER_API_KEY"]
    try:
        import keyring
        return keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
    except Exception:
        return None


def set_api_key(key: str):
    import keyring
    keyring.set_password(KEYRING_SERVICE, KEYRING_USER, key.strip())


def delete_api_key():
    try:
        import keyring
        keyring.delete_password(KEYRING_SERVICE, KEYRING_USER)
    except Exception:
        pass
