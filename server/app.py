"""Billing proxy: the desktop app talks to THIS, never to OpenRouter directly. Your OpenRouter key lives only here (env OPENROUTER_API_KEY).
It checks the license, enforces the plan's monthly AI budget, forces the model, meters real cost, and forwards to OpenRouter."""
from __future__ import annotations
import json, os, secrets, sqlite3, time
from pathlib import Path
import httpx
from fastapi import FastAPI, Header, HTTPException

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
PLANS = json.loads((Path(__file__).parent / "plans.json").read_text())
app = FastAPI(title="NoCode CV proxy")


def db() -> sqlite3.Connection:
    c = sqlite3.connect(os.environ.get("DB_PATH", "licenses.db")); c.row_factory = sqlite3.Row
    c.executescript("""CREATE TABLE IF NOT EXISTS licenses(key TEXT PRIMARY KEY, email TEXT, plan TEXT, active INTEGER DEFAULT 1, created REAL);
                       CREATE TABLE IF NOT EXISTS usage(key TEXT, month TEXT, cost_usd REAL DEFAULT 0, prompt_tokens INTEGER DEFAULT 0,
                                                        completion_tokens INTEGER DEFAULT 0, PRIMARY KEY(key, month));""")
    return c


def forward(payload: dict) -> tuple[int, dict]:
    r = httpx.post(OPENROUTER_URL, headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}", "X-Title": "NoCode CV"}, json=payload, timeout=90)
    return r.status_code, r.json()


def _auth(c: sqlite3.Connection, authorization: str | None):
    key = (authorization or "").removeprefix("Bearer ").strip()
    row = c.execute("SELECT * FROM licenses WHERE key=? AND active=1", (key,)).fetchone()
    if not row: raise HTTPException(401, "Invalid or inactive license")
    return row


def _spent(c, key: str) -> float:
    r = c.execute("SELECT cost_usd FROM usage WHERE key=? AND month=?", (key, time.strftime("%Y-%m"))).fetchone()
    return r["cost_usd"] if r else 0.0


@app.post("/admin/licenses")
def create_license(body: dict, x_admin_token: str | None = Header(None)):
    if not os.environ.get("ADMIN_TOKEN") or x_admin_token != os.environ["ADMIN_TOKEN"]: raise HTTPException(403, "forbidden")
    if body.get("plan") not in PLANS: raise HTTPException(400, f"plan must be one of {[p for p in PLANS if not p.startswith('_')]}")
    key = "ncv_" + secrets.token_urlsafe(24)
    with db() as c: c.execute("INSERT INTO licenses VALUES(?,?,?,1,?)", (key, body.get("email", ""), body["plan"], time.time()))
    return {"license_key": key}      # TODO: call this from your payment provider's webhook after verifying its signature


@app.get("/v1/usage")
def usage(authorization: str | None = Header(None)):
    with db() as c:
        row = _auth(c, authorization); plan = PLANS[row["plan"]]
        return {"plan": row["plan"], "spent_usd": round(_spent(c, row["key"]), 4), "budget_usd": plan["monthly_budget_usd"]}


@app.post("/v1/chat/completions")
def chat(body: dict, authorization: str | None = Header(None)):
    with db() as c:
        row = _auth(c, authorization); plan = PLANS[row["plan"]]
        if _spent(c, row["key"]) >= plan["monthly_budget_usd"]:
            raise HTTPException(402, "Monthly AI credit used up")
        payload = {**body, "model": plan["model"], "max_tokens": min(body.get("max_tokens") or plan["max_tokens"], plan["max_tokens"]),
                   "usage": {"include": True}}            # asks OpenRouter to return the real cost; verify in their docs
        status, data = forward(payload)
        if status != 200: raise HTTPException(502, "AI provider error")
        u = data.get("usage") or {}; pt, ct = u.get("prompt_tokens", 0), u.get("completion_tokens", 0)
        price = plan["price_per_million"]
        cost = u.get("cost") if u.get("cost") is not None else (pt * price["input"] + ct * price["output"]) / 1e6
        c.execute("INSERT INTO usage(key,month) VALUES(?,?) ON CONFLICT DO NOTHING", (row["key"], time.strftime("%Y-%m")))
        c.execute("UPDATE usage SET cost_usd=cost_usd+?, prompt_tokens=prompt_tokens+?, completion_tokens=completion_tokens+? WHERE key=? AND month=?",
                  (cost, pt, ct, row["key"], time.strftime("%Y-%m")))
        return data
