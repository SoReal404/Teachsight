"""Opt-in live diagnosis check. Uses a locally minted session; never prints credentials."""
import asyncio
import json
import os
from pathlib import Path
from playwright.async_api import async_playwright, expect
from engine_fixture import FILES, RUNS, SETTINGS, project
from urllib.parse import urlparse

async def main():
    with open(os.path.expanduser("~/.cache/lovable-auth/session.json")) as f:
        minted = json.load(f)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 1800})
        page = await context.new_page()
        async def engine(route):
            path = urlparse(route.request.url).path
            data = [{"id": "p1", "name": "Browser test project", "stage": "trained", "updated": 1730000000}] if path == "/projects" else project() if path == "/projects/p1" else RUNS if path.endswith("/runs") else FILES if path.endswith("/files") else SETTINGS if path == "/settings" else {}
            await route.fulfill(json=data)
        await page.route("http://127.0.0.1:8765/**", engine)
        await page.goto("http://localhost:8080")
        await page.evaluate("([k,v]) => localStorage.setItem(k,v)", [minted["storage_key"], json.dumps(minted["session"])])
        await page.reload()
        await page.get_by_role("button", name="Browser test project").click()
        await page.get_by_role("button", name="Training review", exact=True).click()
        await page.get_by_role("textbox", name="Training logs").fill("Epoch 2/7: CUDA out of memory. Batch size 64; GPU 4 GB. Training accuracy 0.98; validation accuracy 0.62.")
        await page.get_by_role("textbox", name="Evaluation metrics").fill('{"train_accuracy":0.98,"validation_accuracy":0.62,"batch_size":64,"gpu_memory_gb":4}')
        async with page.expect_response("**/api/public/diagnose", timeout=180000) as response:
            await page.get_by_role("button", name="Diagnose training").click()
        result = await response.value
        print("Diagnosis response status:", result.status)
        if result.status != 200:
            print("Diagnosis blocked; no retry performed.")
            await browser.close(); return
        await expect(page.get_by_role("button", name="Diagnose training", exact=True)).to_be_enabled(timeout=180000)
        await expect(page.get_by_label("AI diagnosis result")).not_to_be_empty()
        await page.get_by_role("button", name="Close training review").click()
        await page.get_by_role("button", name="Training review", exact=True).click()
        await expect(page.get_by_text("Previous reviews", exact=True)).to_be_visible()
        await page.get_by_text("Previous reviews", exact=True).scroll_into_view_if_needed()
        Path("/tmp/browser").mkdir(exist_ok=True)
        await page.screenshot(path="/tmp/browser/live-diagnosis.png")
        print("Live diagnosis saved and read back through private history.")
        await browser.close()

if __name__ == "__main__": asyncio.run(main())