import asyncio
import json
import unittest
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright, expect
from engine_fixture import FILES, RUNS, SETTINGS, job, project

class TeachsightBrowserTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.pw = await async_playwright().start()
        self.browser = await self.pw.chromium.launch(headless=True)
        self.context = await self.browser.new_context(viewport={"width": 1280, "height": 1800})
        self.page = await self.context.new_page()
        self.errors = []
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        self.offline = False; self.settings_fail = False; self.project_fail = False
        self.with_job = False; self.job_status = "running"; self.job_count = 0
        self.job_fail = False; self.active_jobs = 0; self.max_jobs = 0
        await self.page.route("http://127.0.0.1:8765/**", self.engine)
        await self.page.goto("http://localhost:8080", wait_until="domcontentloaded")
        await expect(self.page.get_by_role("heading", name="Your projects")).to_be_visible()

    async def asyncTearDown(self):
        self.assertEqual(self.errors, [], "Browser runtime errors")
        await self.browser.close(); await self.pw.stop()

    async def engine(self, route):
        path = urlparse(route.request.url).path
        if self.offline: await route.abort(); return
        if path == "/projects": data = [{"id": "p1", "name": "Browser test project", "stage": "trained", "updated": 1730000000}]
        elif path == "/settings":
            if self.settings_fail: await route.fulfill(status=500, json={"detail": "Settings unavailable"}); return
            data = SETTINGS
        elif path == "/projects/p1":
            if self.project_fail: await route.fulfill(status=404, json={"detail": "Project missing"}); return
            data = project(self.with_job)
        elif path.endswith("/runs"): data = RUNS
        elif path.endswith("/files"): data = FILES
        elif path.endswith("/model-info"): data = {"has_model": False}
        elif path.endswith("/diagnosis"): data = {"options": [], "summary": "Baseline evaluation"}
        elif path.endswith("/agent"): await route.fulfill(status=500, json={"detail": {"code": "error", "message": "AI engine unavailable"}}); return
        elif path == "/jobs/job-1":
            self.job_count += 1; self.active_jobs += 1; self.max_jobs = max(self.max_jobs, self.active_jobs)
            await asyncio.sleep(0.15)
            self.active_jobs -= 1
            if self.job_fail: await route.fulfill(status=503, json={"detail": "Temporary engine failure"}); return
            data = job(self.job_status, min(99, self.job_count * 10))
        elif path.startswith("/jobs/job-1/"):
            self.job_status = {"pause": "paused", "resume": "running", "cancel": "cancelled"}[path.rsplit("/", 1)[-1]]; data = {}
        else: data = {}
        await route.fulfill(json=data)

    async def open_project(self):
        await self.page.get_by_role("button", name="Browser test project").click()
        await expect(self.page.get_by_role("button", name="Training review", exact=True)).to_be_visible()

    async def test_every_screen_and_pdf(self):
        await self.page.get_by_role("button", name="+ New project").first.click()
        await expect(self.page.get_by_role("heading", name="What do you want to build?")).to_be_visible()
        await self.page.get_by_role("button", name="Sort pictures into groups").click()
        await expect(self.page.get_by_role("button", name="Change type")).to_be_visible()
        await self.page.get_by_role("button", name="Change type").click()
        await self.page.get_by_role("button", name="I’m not sure").click()
        await expect(self.page.get_by_role("heading", name="Let’s find the right type")).to_be_visible()
        await self.page.get_by_role("button", name="Back", exact=True).click()
        await self.page.get_by_role("button", name="Cancel", exact=True).click()
        await self.page.get_by_text("Settings", exact=True).click()
        await expect(self.page.get_by_role("heading", name="Settings")).to_be_visible()
        await self.page.get_by_text("All projects", exact=True).click()
        await self.open_project()
        for chapter in ["Data", "Check", "Plan", "Train", "Test", "Improve"]:
            await self.page.get_by_role("navigation", name="Progress").get_by_role("button", name=chapter).click()
        await self.page.get_by_text("Advanced", exact=True).click()
        for tab in ["train.py", "predict.py (CLI)", "serve.py (Web API)", "README.md", "config.yaml"]:
            await self.page.get_by_text(tab, exact=True).first.click()
        await self.page.get_by_role("button", name="Ask AI", exact=True).click()
        await self.page.get_by_role("textbox", name="Your question").fill("Explain this training failure")
        await self.page.get_by_role("button", name="Send", exact=True).click()
        await expect(self.page.get_by_text("AI engine unavailable", exact=True)).to_be_visible()
        await self.page.get_by_role("button", name="Close drawer").click()
        await self.page.get_by_role("button", name="Training review", exact=True).click()
        await expect(self.page.get_by_text("Sign in to submit a private training review.")).to_be_visible()
        await expect(self.page.get_by_role("button", name="Download PDF report")).to_be_enabled()
        async with self.page.expect_download() as download:
            await self.page.get_by_role("button", name="Download PDF report").click()
        target = Path("/tmp/browser/run-report.pdf"); target.parent.mkdir(parents=True, exist_ok=True)
        await (await download.value).save_as(target)
        self.assertTrue(target.read_bytes().startswith(b"%PDF")); self.assertGreater(target.stat().st_size, 1000)
        await self.page.get_by_role("combobox", name="Training run").select_option("run-2")
        await expect(self.page.get_by_role("button", name="Download PDF report")).to_be_enabled()
        await self.page.screenshot(path="/tmp/browser/training-review.png")

    async def test_connection_recovery_and_settings_errors(self):
        self.offline = True
        await self.page.reload()
        await expect(self.page.get_by_text("Engine not connected.", exact=True)).to_be_visible()
        self.offline = False
        await self.page.get_by_role("button", name="Retry now").click()
        await expect(self.page.get_by_text("Engine not connected.", exact=True)).to_have_count(0)
        self.settings_fail = True
        await self.page.get_by_text("Settings", exact=True).click()
        await expect(self.page.get_by_text("Couldn't load your settings.")).to_be_visible()
        self.settings_fail = False
        await self.page.get_by_role("button", name="Try again", exact=True).click()
        await expect(self.page.get_by_text("Behaviour", exact=True)).to_be_visible()

    async def test_project_error(self):
        self.project_fail = True
        await self.page.get_by_role("button", name="Browser test project").click()
        await expect(self.page.get_by_role("alert")).to_have_text("Project missing")
        self.project_fail = False
        await self.page.get_by_role("button", name="Retry project").click()
        await expect(self.page.get_by_role("button", name="Training review")).to_be_visible()

    async def test_polling_controls_and_cancel(self):
        self.with_job = True
        await self.open_project()
        await self.page.get_by_role("button", name="Pause", exact=True).click()
        await expect(self.page.get_by_role("button", name="Resume", exact=True)).to_be_visible()
        await self.page.get_by_role("button", name="Resume", exact=True).click()
        await expect(self.page.get_by_role("button", name="Pause", exact=True)).to_be_visible()
        await self.page.get_by_role("button", name="Cancel", exact=True).click()
        await expect(self.page.get_by_role("button", name="Pause", exact=True)).to_have_count(0)
        count = self.job_count
        await self.page.wait_for_timeout(3500)
        self.assertEqual(self.job_count, count); self.assertEqual(self.max_jobs, 1)

    async def test_polling_failure_and_reconnect(self):
        self.with_job = True
        await self.open_project()
        await expect(self.page.get_by_role("button", name="Pause", exact=True)).to_be_visible()
        self.job_fail = True
        await expect(self.page.get_by_text("Lost contact with the engine while training.", exact=False).first).to_be_visible(timeout=18000)
        self.job_fail = False; self.job_status = "failed"
        await expect(self.page.get_by_text("Your graphics card ran out of memory.", exact=False)).to_be_visible(timeout=8000)
        count = self.job_count
        await self.page.wait_for_timeout(3500)
        self.assertEqual(self.job_count, count); self.assertEqual(self.max_jobs, 1)

    async def test_polling_done_stops(self):
        self.with_job = True
        await self.open_project()
        await expect(self.page.get_by_role("button", name="Pause", exact=True)).to_be_visible()
        self.job_status = "done"
        await expect(self.page.get_by_role("button", name="Pause", exact=True)).to_have_count(0, timeout=8000)
        count = self.job_count
        await self.page.wait_for_timeout(3500)
        self.assertEqual(self.job_count, count)

    async def test_mobile_review_fits(self):
        await self.page.set_viewport_size({"width": 665, "height": 845})
        await self.open_project()
        await self.page.get_by_role("button", name="Training review", exact=True).click()
        box = await self.page.get_by_role("dialog", name="Training review").bounding_box()
        self.assertGreaterEqual(box["x"], 0); self.assertLessEqual(box["width"], 665)
        heading = self.page.get_by_role("heading", name="Training review")
        await expect(heading).to_be_visible()
        self.assertTrue(await heading.evaluate("el => {const r=el.getBoundingClientRect(); return el.contains(document.elementFromPoint(r.x+5,r.y+5));}"))
        await self.page.screenshot(path="/tmp/browser/training-review-mobile.png")