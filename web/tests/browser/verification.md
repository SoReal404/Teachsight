# Verification

- All seven Playwright cases pass against the running application with deterministic engine fixtures.
- Six Vitest assertions pass for routing, submission validation, ownership helper, and exported run data.
- Live OpenAI Responses call through the copied server helper returned a diagnosis identifying memory pressure and the train/validation gap, recommending batch size 16 instead of 64.
- The application diagnosis endpoint rejects unsigned requests with HTTP 401.
- Cloud test-account creation failed, so authenticated submission persistence and history readback remain unverified. The opt-in live script exercises that flow after a session is available.
- Downloaded PDF is nonempty and starts with a PDF signature. Both pages were rendered and inspected: no clipped lines or overlapping text. The run record continues across pages by design.
- Visual inspection caught the sidebar covering the review panel on a 665×845 screen; rendering the panel outside that stacking context fixed it. Added a browser assertion that its title is actually unobstructed.
- Screens and polling tests use engine fixtures; no real local Python training engine was available.