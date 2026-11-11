# Teachsight / NoCode CV — Repository Audit (v0.4)

Date: 2026-11-11 · No code was changed for this audit. Everything below was read from the
repo and verified by running the existing toolchain.

Repo root: `Teachsight/Teachsight/` (the workspace folder contains one nested copy).

---

## 1. File map

| Path | What it is | State |
|---|---|---|
| `engine/app/main.py` | FastAPI app, all HTTP routes (projects, data, plan, approve, predict, diagnose, jobs) | works |
| `engine/app/dataset.py` | Folder scanning: class folders, split folders, YOLO detection sets, duplicates, balance | works |
| `engine/app/flow.py` | Guided flow: ingest → roles → balance → plan | works |
| `engine/app/training.py` | Model build, loaders, train loop, evaluation, ONNX export | works **for classification only** |
| `engine/app/runner.py` | One job end-to-end (scan → config → train → evaluate → export) | works |
| `engine/app/jobs.py` | Job state machine: steps, %, ETA, pause/resume/cancel, pause-and-ask | works |
| `engine/app/codegen.py` | Writes the export bundle (`train.py`, `predict.py`, `serve.py`, `README.md`) | works, but a single monolithic script |
| `engine/app/agent.py` | OpenRouter chat agent + tool dispatch | works, single provider only |
| `engine/app/hardware.py` | GPU/VRAM/RAM/disk probe, device + batch-size recommendation | works |
| `engine/app/improve.py` | Model Doctor: diagnosis + one-click config changes | works |
| `engine/app/projects.py` | Local project folders under `%LOCALAPPDATA%\NoCodeCV\projects` | works |
| `engine/app/settings.py` | Settings + API key via OS keychain | works (license key is stored in plain text) |
| `engine/app/predict.py` | Inference for trained and pretrained models | works |
| `engine/tests/` | 20 tests | **2 fail** (see §4) |
| `desktop/src/*.tsx` | React UI: Dashboard, Wizard (questionnaire), Workspace (story), Advanced, AskAI, MindMap, Settings | works |
| `desktop/src/*.js` | **Compiled `tsc` output committed next to the sources** | shadows the `.tsx` in dev (see §4) |
| `desktop/src-tauri/src/runtime.rs` | Rust helper for first-run runtime install + engine start | draft, no Tauri project |
| `runtime/setup_runtime.ps1` | One-time Python 3.11 + torch install via `uv` | works, untested end-to-end |
| `server/` | Billing proxy (licenses, monthly budget, OpenRouter metering) | works, not needed for MVP |
| `docs/PRICING.md` | Proxy pricing notes | placeholder numbers |

Missing entirely (no files, no stubs): video handling, webcam capture, dataset search,
collection plans, evaluation lock/hashing, pre-run code validation, AI code-edit loop,
cost estimation/caps, Free/Pro flags, logs/diagnostics, packaging/installer.

---

## 2. What genuinely works today (verified)

1. **End-to-end classification loop** — Wizard → workspace → data → check → plan → train →
   test → improve, all driven by the engine over HTTP. The UI and the API agree.
2. **Folder intelligence** — class folders, `training_set`/`test_set` layouts, role chips,
   broken-image detection, exact-duplicate detection, cross-split duplicate warnings.
3. **Honest evaluation** — accuracy, precision, recall, F1, confusion matrix, per-class
   metrics, val loss, inference speed, model size, and a separate "final exam" score when an
   exam folder exists.
4. **Job control** — live ETA, pause, resume, cancel, and pause-and-ask with click options.
5. **Export bundle** — `best.pt`, `labels.json`, `config.yaml`, `report.json`, plus a
   standalone `predict.py` CLI, a `serve.py` REST API with a browser demo page, and a
   coder README. `config.yaml` is genuinely the single source of truth.
6. **Hardware probe** — real CUDA allocation test, VRAM-based batch sizing, CPU fallback.
7. **Key storage** — the OpenRouter key is in the Windows keychain, not in a file.
8. **Frontend compiles clean** — `tsc --noEmit` passes with zero errors.

Verification I ran:

- `tsc --noEmit -p tsconfig.json` → **exit 0**, no errors.
- `pytest` in `engine/` (Anaconda env `deep`, Python 3.10.20, torch 2.5.1, CUDA available)
  → **17 passed, 2 failed** (both failures explained in §4).
- `git log` → **zero commits**. The repo is initialized but has no history.

---

## 3. Gaps against the four phases

### Phase 1 — Safe engine

| Requirement | Status |
|---|---|
| MVP types: classification, detection, segmentation | **Wrong.** `questions.ts:9` marks `detection` as "Ready" but detection training is broken (§4.1). Segmentation is "Coming soon" (it is supposed to be MVP). |
| Modular training template (data / augmentation / model / loss / loop / eval) | **Missing.** `codegen.py:9-61` writes one flat `train.py`. |
| Locked evaluation module + hash proof | **Missing.** No hash, no lock anywhere. |
| Grouped splits (video id, source folder, near-dup cluster) | **Missing.** `training.py:43-50` splits per image, stratified by class only. |
| Pre-run checks: `ast` parse, `inspect` signatures, ruff/pyflakes, smoke test, `DeprecationWarning` as error | **Missing.** No validation layer exists. |
| 3 repair attempts then rollback | **Missing.** |
| Version code + metrics, keep only if it improves | **Partial.** Runs are kept in `runs/`, but `improve.apply` (`improve.py:167`) changes config with no metric gate and no rollback. |
| Two AI modes (safe / free edit) with safe as default | **Partial.** `plan`/`code` modes exist, but "code" means full access and the AI can only tweak hyperparameters — it cannot edit code at all. |
| Pinned libraries + version manifest in every prompt | **Missing.** `requirements-base.txt` uses `>=` ranges; torch is not even in it. |
| GPU/VRAM/RAM/disk detection | **Done.** |
| OOM → reduce batch size automatically | **Missing.** `training.py:260-267` only raises a message telling the user to lower it manually. |
| CPU fallback with honest ETA | **Partial.** Device selection + benchmark ETA exist. |
| Per-project API cost estimate + user-set hard cap | **Missing** in the app (the proxy has a monthly budget, not a user cap). |
| Report card: per-class, worst failure images, "data it has not seen" | **Partial.** Per-class + confusion matrix exist; worst failures and the unseen-data statement do not. |

### Phase 2 — Project without data

- "No data yet" project state: **Missing.** `flow.ingest` requires a path; there is no
  collection plan, no webcam capture, no dataset search, and no data-threshold logic that
  gates the Train button.
- No Google/Bing scraping: **OK** (nothing exists to violate this).

### Phase 3 — Video as data

- **Entirely missing.** `dataset.IMG_EXT` has no video extensions; no frame extraction, no
  blur/darkness/duplicate filtering, no video-id grouping, no time-range labeler, no review
  queue. `predict.py`'s docstring mentions video frames but there is no implementation.

### Phase 4 — Tester-ready

- First-run setup: **Partial.** `runtime/setup_runtime.ps1` is a good script (private
  Python 3.11 via `uv`, CUDA-wheel detection by driver version), but it has no resume, no
  per-step failure messages, and no UI to drive it — the Rust side that would call it has no
  Tauri project around it.
- API key wizard: **Partial.** Key entry + keychain storage exist; there is no provider
  choice (Gemini/OpenRouter/other), no "test the key" button, no Gemini guide.
- Free vs Pro flags: **Missing.**
- Local project saving: **Done.** GitHub backup: **Missing.**
- Rotating logs, "Copy diagnostics", feedback button: **Missing.**
- Model + ONNX export + usage snippet: **Partial.** ONNX export is attempted and silently
  swallowed on failure (`training.py:309-310`), so a failed export looks like success in the UI.
- Packaging: **Missing.** `desktop/src-tauri/` contains exactly one file (`runtime.rs`).
  There is no `Cargo.toml`, no `tauri.conf.json`, no `main.rs`, no installer. The product is
  currently a browser app plus a local FastAPI server.

---

## 4. Concrete bugs found

**4.1 Detection is advertised as trainable but cannot train.** `questions.ts:9` puts
`detection` in `READY`, so the UI enables "Start training" for it. But `training.train()`
always uses `CrossEntropyLoss` on `model(x)` (`training.py:202`, `training.py:220-221`),
which is meaningless for a detection model. Two distinct failures follow:
- A real YOLO dataset resolves to `train_dir = dataset root` (`dataset.py:371-387`), then
  `datasets.ImageFolder(root)` treats the `images/` folder as a single class and trains a
  classifier on it.
- A plain class-folder dataset with a detection brief produces an SSDLite model and then
  crashes in the loss computation with a raw Python traceback in the UI.

**4.2 Committed `.js` shadows the `.tsx` sources.** `tsconfig.json` has no `outDir` and no
`noEmit`, so `npm run build` (= `tsc && vite build`, `desktop/package.json:8`) writes
compiled `.js` next to every `.tsx` in `src/`. Vite resolves `.js` before `.tsx`, so
`npm run dev` serves the last-built JavaScript, not your edits. Proof: `engine.ts` was
edited at 21:01, `engine.js` was built at 20:08, and `engine.js` is missing the `hardware`
method that exists in `engine.ts`. The shipped `dist/` bundle (20:08) likewise contains no
`/hardware` or `createSampleProject` route. Fixing this is a 2-line tsconfig change
(`noEmit: true`) plus deleting the stale files.

**4.3 Two failing tests.**
- `test_agent.py::test_missing_key_message` expects HTTP 400 `no_key` but gets 200. Cause:
  a real OpenRouter key (`sk-or-v1-…`) is stored in this machine's Windows Credential
  Manager, so `settings.get_api_key()` returns it and the test makes a live API call.
  Not an app bug — but it means the "missing key" flow cannot be exercised on this
  machine, and it burns a little credit on every run.
- `test_flow.py::test_exam_training_predict_correct_and_improve` fails with `KeyError:
  'source'`. Cause: `improve.diagnose` no longer returns a `source` field, but the test
  still asserts it. Code/test drift — the test is stale, not the engine.

**4.4 License key stored in plain text.** `settings.py:12` keeps `license_key` in
`settings.json`, which contradicts the "never plain text" rule (the OpenRouter key is
correctly in the keychain).

**4.5 Duplicate detection is exact-bytes only.** `dataset.py:303` uses an MD5 of the file
bytes. Re-encoded or slightly edited copies are missed, which is exactly the near-duplicate
leak that inflates the exam score.

**4.6 Deprecated FastAPI pattern in the exported bundle.** The generated `serve.py` uses
`@app.on_event("startup")`, deprecated in FastAPI ≥0.93. It will break on the pinned
versions once `DeprecationWarning`-as-error checking is introduced in Phase 1.

**4.7 Wildcard CORS with credentials in the exported `serve.py`.**
`allow_origins=["*"]` together with `allow_credentials=True` produces a response browsers
reject for cross-origin calls — the website integration the README promises would fail.

**4.8 The `Improve` docs promise jitter.** `improve.py:176` for "regularize" only halves
the learning rate, but the user-facing text says it "applies gentle data jitter".

**4.9 No rollback history.** Git has zero commits, and `runs/` only keeps successful runs.
"Always allow rollback" (Phase 1) is impossible today: there is no version manifest, no
code snapshot, and no metric-gated promotion.

**4.10 No dependency pinning anywhere.** `requirements-base.txt`, `server/requirements.txt`
and the generated bundle's `requirements.txt` all use `>=`. A tester installing tomorrow
can get different library versions than the ones this code was written against.

---

## 5. Acceptance-test status today

| # | Test | Status |
|---|---|---|
| 1 | Clean machine, no Python → install → "ready to train" in ~10 min | **Fail** — no installer, no packaged app |
| 2 | Project with no data: saves, plan appears, Train disabled, webcam works | **Fail** — no-data path and webcam do not exist |
| 3 | Two videos → frames extracted, deduped, split by video id, trains | **Fail** — no video support |
| 4 | Injected deprecated API call caught, repaired or rolled back | **Fail** — no pre-run validation |
| 5 | Evaluation module hash unchanged after AI edits | **Fail** — no locked module |
| 6 | Simulated OOM reduces batch size automatically | **Fail** — message only |
| 7 | Missing/wrong API key → friendly recovery | **Partial** — wrong key → 401 → friendly message + Settings button works; missing key cannot be reproduced here (4.3) |
| 8 | Spending cap stops further AI calls | **Fail** — no user-set cap in the app |

---

## 6. Recommended Phase 1 order (small, reviewable steps)

1. **Unblock the build**: `noEmit` in tsconfig, delete the stale `src/*.js`, make `dev` and
   `build` agree; commit the current state so rollback exists from day one.
2. **Type honesty**: mark `detection` "Coming soon" in `questions.ts` until the detection
   path actually trains; segment MVP to classification first.
3. **Locked evaluation module**: extract `evaluate()` + the split into a separate module
   (`engine/app/evaluation.py`) with a SHA-256 manifest entry, and reject any AI edit that
   touches it.
4. **Pre-run validation**: `ast` parse → `inspect` signature check → ruff → tiny smoke
   test with `DeprecationWarning` as error, before every real run.
5. **Grouped splits**: split by video id / source folder, with the random per-image split
   only as the fallback when no groups exist.
6. **Robust training**: OOM → halve the batch size and retry automatically (up to 3 times),
   then fall back to CPU with an honest ETA; `num_workers=0` on Windows by default.
7. **Pinned versions**: exact pins in `requirements-base.txt` + a `versions.json` manifest
   that is injected into every AI prompt.
8. **Versioned runs + metric gate**: snapshot the code with each run, keep a change only if
   the score improves beyond a noise margin, and always keep the previous run recoverable.
9. **Provider + cost**: Gemini / OpenRouter / custom endpoint, a per-project cost estimate,
   and a user-set hard cap enforced before each AI call.
10. **Report card**: per-class metrics, worst failure images, and a plain statement of what
    the model has never seen.

## 7. Decisions needed from you before Phase 1 starts

- **Scope of the first real MVP**: classification only, or classification + detection +
  segmentation (as the brief asks)? Detection and segmentation are each a substantial
  separate build; classification-only is the fastest route to a tester in 10 minutes.
- **Packaging target**: Tauri (Rust) as `runtime.rs` implies, or a simpler signed
  installer that ships the engine + a browser window? Tauri is already half-written.
- **Provider**: keep OpenRouter only for the MVP, or add Gemini now (free tier matters for
  testers without a paid key)?
