# Browser regression suite

With the app running on port 8080, run `python3 -m unittest discover -s tests/browser -p 'test_*.py' -v`.
Install `tests/browser/requirements.txt` and Chromium on your own machine first. The Lovable sandbox already includes them.

The suite intercepts only engine requests, leaving the actual application running. It checks the dashboard, type picker, questionnaire, guided picker, Settings, all six workspace chapters, Advanced file tabs, Ask AI, training review, PDF download, connection recovery, non-overlapping polling, terminal-state shutdown, pause/resume/cancel and error states. No AI credits are consumed by regression tests.

Run `tests/browser/live_diagnosis.py` separately with a locally minted Cloud session available to verify a real AI request. This consumes AI credits and stores the submitted sample in that account's private history.