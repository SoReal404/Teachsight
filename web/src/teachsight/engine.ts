const KEY = "teachsight_engine_url";
const DEFAULT = "http://127.0.0.1:8765";
export function getEngineUrl(): string {
  if (typeof window === "undefined") return DEFAULT;
  return (localStorage.getItem(KEY) || DEFAULT).replace(/\/+$/, "");
}
export function setEngineUrl(u: string) {
  localStorage.setItem(KEY, u.trim() || DEFAULT);
  window.dispatchEvent(new Event("teachsight_engine_changed"));
}
export class EngineError extends Error { constructor(public code: string, message: string) { super(message); } }

const FRIENDLY = {
  offline: "I can't reach the engine. Make sure it's running on your computer, then try again.",
  timeout: "The engine took too long to answer. It may be busy — try again in a moment.",
};

/** Turns raw engine/Python errors into something a person can act on. */
export function friendly(msg: string): string {
  const m = (msg || "").toLowerCase();
  if (m.includes("out of memory") || m.includes("cuda oom") || m.includes("cuda error: out")) return "Your graphics card ran out of memory. Try a smaller model or fewer pictures per step, then train again.";
  if (m.includes("no such file") || m.includes("not found") && m.includes("folder")) return "A picture folder couldn't be found. Check the folder still exists and pick it again.";
  if (m.includes("no module named")) return "The engine is missing a library (" + msg.split("named").pop()?.trim() + "). Re-run the runtime installer.";
  return msg;
}

async function call<T>(path: string, method = "GET", body?: unknown, timeoutMs = 30000): Promise<T> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  let r: Response;
  try {
    const init: RequestInit = { method, signal: ctrl.signal };
    if (body !== undefined) { init.headers = { "Content-Type": "application/json" }; init.body = JSON.stringify(body); }
    r = await fetch(getEngineUrl() + path, init);
  } catch (e: any) {
    throw e?.name === "AbortError" ? new EngineError("timeout", FRIENDLY.timeout) : new EngineError("offline", FRIENDLY.offline);
  } finally { clearTimeout(t); }
  if (!r.ok) {
    let d: any = null; try { d = (await r.json()).detail; } catch { /* ignore */ }
    const raw = d?.message ?? (typeof d === "string" ? d : `Engine error ${r.status}`);
    throw new EngineError(d?.code ?? "error", friendly(raw));
  }
  return r.json();
}
const post = <T,>(p: string, b: unknown = {}, ms?: number) => call<T>(p, "POST", b, ms);
const B = () => getEngineUrl();

export const engine = {
  ping: () => call<any>("/hardware", "GET", undefined, 4000),
  setData: (id: string, path: string) => post<any>(`/projects/${id}/data`, { path }, 120000),
  setRoles: (id: string, roles: Record<string, string>) => call<any>(`/projects/${id}/roles`, "PUT", { roles }),
  confirm: (id: string) => post<any>(`/projects/${id}/confirm`),
  plan: (id: string) => post<any>(`/projects/${id}/plan`, {}, 60000),
  thumb: (id: string, path: string, size = 96) => `${B()}/projects/${id}/thumb?path=${encodeURIComponent(path)}&size=${size}`,
  predict: (id: string, image_b64: string) => post<any>(`/projects/${id}/predict`, { image_b64 }, 60000),
  correct: (id: string, image_b64: string, label: string) => post<any>(`/projects/${id}/correct`, { image_b64, label }),
  diagnosis: (id: string) => call<any>(`/projects/${id}/diagnosis`),
  improve: (id: string, action: string) => post<any>(`/projects/${id}/improve`, { action }),
  projects: () => call<any[]>("/projects", "GET", undefined, 8000),
  createProject: (name: string, brief: any) => post<any>("/projects", { name, brief }),
  createSampleProject: () => post<any>("/projects/sample", {}, 120000),
  hardware: () => call<any>("/hardware"),
  deleteProject: (id: string) => call<any>(`/projects/${id}`, "DELETE"),
  kickoff: (id: string) => post<any[]>(`/projects/${id}/kickoff`),
  project: (id: string) => call<any>(`/projects/${id}`),
  talk: (id: string, message: string, mode: string) => post<any>(`/projects/${id}/agent`, { message, mode }, 120000),
  choose: (id: string, option_id: string) => post<any>(`/projects/${id}/choice`, { option_id }),
  approve: (id: string) => post<any>(`/projects/${id}/approve`, {}, 60000),
  job: (id: string) => call<any>(`/jobs/${id}`, "GET", undefined, 10000),
  answer: (id: string, answer: string) => post<any>(`/jobs/${id}/answer`, { answer }),
  control: (id: string, a: "pause" | "resume" | "cancel") => post<any>(`/jobs/${id}/${a}`),
  runs: (pid: string) => call<any[]>(`/projects/${pid}/runs`),
  runFiles: (pid: string, rid: string) => call<Record<string, string>>(`/projects/${pid}/runs/${rid}/files`),
  rerun: (pid: string, rid: string, config_yaml: string) => post<any>(`/projects/${pid}/runs/${rid}/rerun`, { config_yaml }, 60000),
  settings: () => call<any>("/settings"),
  saveSettings: (s: any) => call<any>("/settings", "PUT", s),
  saveKey: (key: string) => call<any>("/settings/api-key", "PUT", { key }),
  removeKey: () => call<any>("/settings/api-key", "DELETE"),
  saveProviderKey: (provider: string, key: string) => call<any>("/settings/provider-key", "PUT", { provider, key }),
  removeProviderKey: (provider: string) => call<any>(`/settings/provider-key?provider=${encodeURIComponent(provider)}`, "DELETE"),
  testProviderKey: (provider: string, key?: string, base_url?: string) => post<any>("/settings/test-key", { provider, key, base_url }, 60000),
  usePretrained: (id: string) => post<any>(`/projects/${id}/pretrained`, {}, 120000),
  modelInfo: (pid: string) => call<any>(`/projects/${pid}/model-info`),
  openModelFolder: (pid: string) => post<any>(`/projects/${pid}/open-folder`),
  exportZipUrl: (pid: string, rid?: string) => `${B()}/projects/${pid}/export-zip${rid ? `?rid=${rid}` : ""}`,
};
