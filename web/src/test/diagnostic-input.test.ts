import { describe, expect, it } from "vitest";
import { diagnosticInput, ownsSubmission } from "@/lib/diagnostic-input";
import { buildRunReport } from "@/teachsight/run-report";

describe("Private training reviews", () => {
  it("allows the owner to read their submission", () => { expect(ownsSubmission("owner-a", "owner-a")).toBe(true); });
  it("does not allow another owner to read the submission", () => { expect(ownsSubmission("owner-a", "owner-b")).toBe(false); });
  it("rejects empty training logs", () => { expect(diagnosticInput.safeParse({ projectId: "p", projectName: "P", logs: " ", metrics: {} }).success).toBe(false); });
  it("accepts submitted numeric evaluation metrics", () => { expect(diagnosticInput.parse({ projectId: "p", projectName: "P", logs: "CUDA out of memory", metrics: { accuracy: 0.82 } }).metrics).toEqual({ accuracy: 0.82 }); });
  it("exports selected run settings, progress, and evaluation in a PDF", async () => {
    const blob = buildRunReport("Plants", { id: "run-2", metrics: { accuracy: 0.82 }, progress: { epoch: 7 } }, { "config.yaml": "batch_size: 16" });
    const text = await new Promise<string>((resolve) => { const r = new FileReader(); r.onload = () => resolve(String(r.result)); r.readAsText(blob); });
    expect(text.startsWith("%PDF")).toBe(true);
    expect(text).toContain("batch_size: 16"); expect(text).toContain("epoch"); expect(text).toContain("0.82"); expect(text).toContain("run-2");
  });
});