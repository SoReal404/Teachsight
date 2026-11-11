# NoCode CV (v0.4)

Desktop app that trains image classifiers locally through a chat. Built from the product spec.

```
engine/    Python engine (FastAPI): hardware, dataset checks, AI agent (OpenRouter), projects, training jobs, Advanced-mode files
server/    Billing proxy for paid plans (holds YOUR OpenRouter key, meters usage). See docs/PRICING.md
runtime/   One-time Windows runtime installer (private Python + libraries, installed once)
desktop/   Vite + React UI (chat, settings, advanced) and Rust helpers for Tauri
```

## Where do I put my OpenRouter key?
1. **Dev:** `engine/.env` -> `OPENROUTER_API_KEY=sk-or-...` (copy `engine/.env.example`; never commit it).
2. **In the app:** Settings > "Use my own OpenRouter key" (saved in the Windows keychain).
3. **Customers:** never in the app. Put it on the proxy server (`server/`). Read docs/PRICING.md.
Change the model in Settings (default `openai/gpt-4o-mini`; see openrouter.ai/models).

## Run it (dev)
Engine (Anaconda prompt, env active):
```
cd engine
pip install -r requirements-base.txt
pip install torch torchvision          # GPU build: see pytorch.org
copy .env.example .env                 # then paste your key
uvicorn app.main:app --port 8765
pytest
```
UI (second terminal): `cd desktop && npm install && npm run dev` -> http://localhost:5173

Proxy (only when you test paid plans): `cd server && pip install -r requirements.txt` then set `OPENROUTER_API_KEY` and `ADMIN_TOKEN`, and run `uvicorn app:app --port 9000`.

## How it works now (no chat)
1. **Dashboard** with an animated shader background (shaders.com, MIT). Falls back to a still gradient if WebGPU is unavailable. The background is not used inside a project, so training keeps the GPU.
2. **New project:** the first question is the type (8 cards: classification, detection, segmentation, pose, OCR, enhancement, visual Q and A, or "I'm not sure"). Then 3 to 5 short screens of questions for that type, each with a hover "Why I ask". Question sets live in `desktop/src/questions.ts`. Only classification can be trained today (`READY` in the same file); the other types save your answers.
3. **Project workspace = one scrolling story** (Data, Check, Plan, Train, Test, Improve). Chapters unlock as you finish the previous one; the stepper follows your scroll.
   - **Data:** paste or pick a folder. The engine detects class folders and split folders (training_set, test_set, ...), treats extras like single_prediction as ignored, and shows a mind map. Click a folder's role chip to change it (Training, Validation, Final exam, Ignore). Warns about pictures that appear in both training and exam folders.
   - **Check:** balance bars, hover explanations, and the recommended fix first. One click to choose. Balanced data needs no decision.
   - **Plan:** built from your answers (model, rounds). Click Start.
   - **Train:** live board with ETA, pause, cancel, and pause-and-ask. Failures show a friendly card with Try again.
   - **Test:** score is graded on the exam folder when there is one. Drop in a picture, see predictions, hover the picture and click the right category if the AI is wrong (saved for improvement).
   - **Improve:** rule-based diagnosis (no AI cost) and one-click fixes: train longer, bigger AI, balance, or add pictures and re-check.
4. **Ask AI** is a side drawer (needs the OpenRouter key). The whole flow above works without any AI key.
5. Advanced tab: each run has `config.yaml` and `train.py`; edit and Run again.

## Status
Tested here: 19 engine tests (including split folders, roles, exam grading, predict plumbing, corrections, improve) and 3 proxy tests; the UI compiles, builds, and a simulated click-through passes from dashboard to the plan and the failure card.
Not run yet on a real PC: real PyTorch training, prediction with a real model, the shader on your GPU, the Windows runtime installer, the Tauri/Rust wrapper, a real OpenRouter call.
Not built yet: training error ladder (out of memory etc.) and dry run, share-demo export, ONNX export, detection and the annotation editor, GitHub backup, the other six types' training.
