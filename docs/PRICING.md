# Pricing and your OpenRouter key

## Rule 1: never ship your key inside the app
Anything inside a desktop app can be extracted. If your OpenRouter key is in the installer, someone will find it and you pay their bill. So:

```
Desktop app  --license key-->  YOUR proxy server  --your OpenRouter key-->  OpenRouter
(on customer PC)               (server/, you host it)                         (the AI models)
```

The proxy (`server/app.py`) checks the license, enforces the plan's monthly AI budget, forces the model, caps `max_tokens`, records the real cost, and only then calls OpenRouter. Your key exists only as an environment variable on your server.

## Where the key goes
| Situation | Where |
|---|---|
| You developing and testing | `engine/.env` (copy `.env.example`; git-ignored) |
| A power user with their own key | Settings > "Use my own OpenRouter key" (stored in the Windows keychain) |
| Paying customers | Nothing on their PC. Your key is `OPENROUTER_API_KEY` on the proxy server |

Also set a credit limit on the key in the OpenRouter dashboard as a last safety net.

## What costs you money
- Training runs on the customer's GPU, so it costs you nothing.
- Only the chat text goes to the AI. Cost per customer = calls x tokens x model price.
- Measure it, do not guess: the proxy stores real cost per license per month (`usage` table, `GET /v1/usage`). Run a few real projects, read the average, then set prices.

## Setting a price (formula)
```
monthly_AI_cost_per_active_user   (measured)
price >= AI_cost / (1 - target_margin) + payment_fees + support_time
budget_in_plans.json = AI_cost you are willing to carry for that plan
```
Suggested structure (numbers are yours to choose):
- Free: small budget so people can try one project end to end.
- Pro (monthly): a budget with headroom over the measured average, so heavy users still hit a limit.
- Bring your own key: lower price or one-time license, since the AI cost is theirs.

Cost controls already in the code: model forced by plan, `max_tokens` cap, only the last 20 messages sent, a hard monthly budget (HTTP 402 -> the app shows "out of credits").

## Taking payments
Pick a provider that supports sellers in your country (a merchant-of-record handles tax for you). On a successful payment its webhook should call `POST /admin/licenses` (verify the webhook signature first) and email the license key. On cancel, set `active = 0`.

## Still to build before selling
- Webhook handler and signature check, license email.
- Per-device activation limit and rate limiting.
- Terms of service and privacy policy (the app sends chat text and folder/category names to the AI, never pictures).
- HTTPS hosting for the proxy; move SQLite to Postgres when you have real traffic.
