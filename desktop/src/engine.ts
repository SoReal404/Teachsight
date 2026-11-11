const BASE = (import.meta as any).env?.VITE_ENGINE_URL ?? "http://127.0.0.1:8765";
export class EngineError extends Error { constructor(public code: string, message: string) { super(message); } }

async function call<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const r = await fetch(BASE + path, { method, headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
  if (!r.ok) {
    let d: any = null; try { d = (await r.json()).detail; } catch { /* ignore */ }
    throw new EngineError(d?.code ?? "error", d?.message ?? (typeof d === "string" ? d : `Engine error ${r.status}`));
  }
  return r.json();
}
const post = <T,>(p: string, b: unknown = {}) => call<T>(p, "POST", b);

export const BASE_URL = BASE;
export const engine = {
  setData: (id: string, path: string) => post<any>(`/projects/${id}/data`, { path }),
  setRoles: (id: string, roles: Record<string, string>) => call<any>(`/projects/${id}/roles`, "PUT", { roles }),
  confirm: (id: string) => post<any>(`/projects/${id}/confirm`),
  plan: (id: string) => post<any>(`/projects/${id}/plan`),
  thumb: (id: string, path: string, size = 96) => `${BASE}/projects/${id}/thumb?path=${encodeURIComponent(path)}&size=${size}`,
  predict: (id: string, image_b64: string) => post<any>(`/projects/${id}/predict`, { image_b64 }),
  correct: (id: string, image_b64: string, label: string) => post<any>(`/projects/${id}/correct`, { image_b64, label }),
  diagnosis: (id: string) => call<any>(`/projects/${id}/diagnosis`),
  improve: (id: string, action: string) => post<any>(`/projects/${id}/improve`, { action }),
  projects: () => call<any[]>("/projects"),
  createProject: (name: string, brief: any) => post<any>("/projects", { name, brief }),
  createSampleProject: () => post<any>("/projects/sample"),
  hardware: () => call<any>("/hardware"),
  deleteProject: (id: string) => call<any>(`/projects/${id}`, "DELETE"),
  kickoff: (id: string) => post<any[]>(`/projects/${id}/kickoff`),
  project: (id: string) => call<any>(`/projects/${id}`),
  talk: (id: string, message: string, mode: string) => post<any>(`/projects/${id}/agent`, { message, mode }),
  choose: (id: string, option_id: string) => post<any>(`/projects/${id}/choice`, { option_id }),
  approve: (id: string) => post<any>(`/projects/${id}/approve`),
  job: (id: string) => call<any>(`/jobs/${id}`),
  answer: (id: string, answer: string) => post<any>(`/jobs/${id}/answer`, { answer }),
  control: (id: string, a: "pause" | "resume" | "cancel") => post<any>(`/jobs/${id}/${a}`),
  runs: (pid: string) => call<any[]>(`/projects/${pid}/runs`),
  runFiles: (pid: string, rid: string) => call<Record<string, string>>(`/projects/${pid}/runs/${rid}/files`),
  rerun: (pid: string, rid: string, config_yaml: string) => post<any>(`/projects/${pid}/runs/${rid}/rerun`, { config_yaml }),
  settings: () => call<any>("/settings"),
  saveSettings: (s: any) => call<any>("/settings", "PUT", s),
  saveKey: (key: string) => call<any>("/settings/api-key", "PUT", { key }),
  removeKey: () => call<any>("/settings/api-key", "DELETE"),
  saveProviderKey: (provider: string, key: string) => call<any>("/settings/provider-key", "PUT", { provider, key }),
  removeProviderKey: (provider: string) => call<any>(`/settings/provider-key?provider=${encodeURIComponent(provider)}`, "DELETE"),
  testProviderKey: (provider: string, key?: string, base_url?: string) => post<any>("/settings/test-key", { provider, key, base_url }),
  usePretrained: (id: string) => post<any>(`/projects/${id}/pretrained`),
  modelInfo: (pid: string) => call<any>(`/projects/${pid}/model-info`),
  openModelFolder: (pid: string) => post<any>(`/projects/${pid}/open-folder`),
  exportZipUrl: (pid: string, rid?: string) => `${BASE}/projects/${pid}/export-zip${rid ? `?rid=${rid}` : ""}`,
};
