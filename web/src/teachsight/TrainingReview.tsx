import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { Session } from "@supabase/supabase-js";
import { Download, FlaskConical, Square, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { supabase } from "@/integrations/supabase/client";
import { lovable } from "@/integrations/lovable";
import "@lovable.dev/cloud-auth-js/styles.css";
import { engine } from "./engine";
import { buildRunReport, downloadReport } from "./run-report";

export default function TrainingReview({ pid, projectName, runs, job, onClose }: { pid: string; projectName: string; runs: any[]; job: any; onClose: () => void }) {
  const [session, setSession] = useState<Session | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [logs, setLogs] = useState(job?.error || "");
  const [metrics, setMetrics] = useState(JSON.stringify(runs[0]?.metrics ?? job?.result?.metrics ?? {}, null, 2));
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [rid, setRid] = useState(runs[0]?.id || "");
  const [report, setReport] = useState<Blob | null>(null);
  const [reportBusy, setReportBusy] = useState(false);
  const [history, setHistory] = useState<any[]>([]);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => {
    void supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = supabase.auth.onAuthStateChange((_event, next) => setSession(next));
    return () => { data.subscription.unsubscribe(); controller.current?.abort(); };
  }, []);
  const refreshHistory = async () => {
    const { data, error } = await supabase.from("training_diagnostics").select("id, diagnosis, status, created_at").eq("engine_project_id", pid).order("created_at", { ascending: false }).limit(10);
    if (error) setError(error.message); else setHistory(data || []);
  };
  useEffect(() => { if (session) void refreshHistory(); else setHistory([]); }, [session?.user.id, pid]);
  useEffect(() => {
    let alive = true;
    setReport(null);
    const run = runs.find((r) => r.id === rid);
    if (!run) return;
    setReportBusy(true);
    engine.runFiles(pid, rid).then((files) => {
      if (alive) setReport(buildRunReport(projectName, run, files, job?.result?.run_id === rid || job?.run_id === rid ? job : undefined));
    }).catch((e) => { if (alive) setError(e.message); }).finally(() => { if (alive) setReportBusy(false); });
    return () => { alive = false; };
  }, [rid, runs, pid, projectName, job]);
  async function auth(action: "login" | "signup" | "reset") {
    setError("");
    const result = action === "login" ? await supabase.auth.signInWithPassword({ email, password }) : action === "signup" ? await supabase.auth.signUp({ email, password, options: { emailRedirectTo: window.location.origin } }) : await supabase.auth.resetPasswordForEmail(email, { redirectTo: window.location.origin + "/auth" });
    if (result.error) setError(result.error.message);
    else if (action !== "login") setError(action === "signup" ? "Check your email to confirm your account." : "Check your email for the password reset link.");
  }
  async function diagnose() {
    if (!session || busy) return;
    let parsed;
    try { parsed = JSON.parse(metrics); if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") throw new Error(); }
    catch { setError("Evaluation metrics must be a JSON object."); return; }
    setBusy(true); setAnswer(""); setError("");
    const ctrl = new AbortController(); controller.current = ctrl;
    try {
      const response = await fetch("/api/public/diagnose", { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${session.access_token}` }, body: JSON.stringify({ projectId: pid, projectName, logs, metrics: parsed }), signal: ctrl.signal });
      if (!response.ok) { const body = await response.json(); throw new Error(body.message); }
      if (!response.body) throw new Error("No diagnosis was returned.");
      const reader = response.body.getReader(), decoder = new TextDecoder(); let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value, { stream: !done });
        const lines = buffer.split("\n"); buffer = lines.pop() || "";
        for (const line of lines) {
          if (!line.trim()) continue;
          const event = JSON.parse(line);
          if (event.text) setAnswer((a) => a + event.text);
          if (event.error) throw new Error(event.error);
        }
        if (done) break;
      }
      await refreshHistory();
    } catch (e) { if (!ctrl.signal.aborted) setError(e instanceof Error ? e.message : "Diagnosis failed."); }
    finally { setBusy(false); controller.current = null; }
  }
  return createPortal(<aside className="training-review" role="dialog" aria-modal="true" aria-label="Training review">
    <div className="flex items-center justify-between gap-3"><h2>Training review</h2><Button variant="ghost" size="icon" aria-label="Close training review" onClick={onClose}><X /></Button></div>
    <section className="space-y-3 border-b border-border py-5">
      <h3>Run report</h3>
      <select aria-label="Training run" value={rid} onChange={(e) => setRid(e.target.value)}><option value="" disabled>Select a run</option>{runs.map((r) => <option key={r.id} value={r.id}>{r.id}</option>)}</select>
      {!runs.length && <p className="text-muted-foreground">No training runs yet.</p>}
      <Button disabled={!report || reportBusy} onClick={() => { if (report) downloadReport(report, `teachsight-${String(rid).replace(/[^a-zA-Z0-9_-]/g, "_")}.pdf`); }}><Download />{reportBusy ? "Preparing report…" : "Download PDF report"}</Button>
    </section>
    <section className="space-y-3 py-5">
      <h3>AI diagnosis</h3>
      {!session ? <div className="space-y-3">
        <p className="text-muted-foreground">Sign in to submit a private training review.</p>
        <input aria-label="Email" type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <input aria-label="Password" type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <div className="flex flex-wrap gap-2"><Button onClick={() => auth("login")}>Sign in</Button><Button variant="outline" onClick={() => auth("signup")}>Create account</Button><Button variant="link" onClick={() => auth("reset")}>Reset password</Button></div>
        <Button variant="outline" className="w-full" onClick={async () => { const r = await lovable.auth.signInWithOAuth("google", { redirect_uri: window.location.origin }); if (r.error) setError(r.error.message); }}><svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24"><path fill="#4285F4" d="M23.49 12.27c0-.79-.07-1.54-.19-2.27H12v4.51h6.47c-.29 1.48-1.14 2.73-2.4 3.58v3h3.86c2.26-2.09 3.56-5.17 3.56-8.82z"/><path fill="#34A853" d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.86-3c-1.08.72-2.45 1.16-4.07 1.16-3.13 0-5.78-2.11-6.73-4.96H1.29v3.09C3.26 21.3 7.31 24 12 24z"/><path fill="#FBBC05" d="M5.27 14.29c-.25-.72-.38-1.49-.38-2.29s.14-1.57.38-2.29V6.62H1.29C.47 8.24 0 10.06 0 12s.47 3.76 1.29 5.38l3.98-3.09z"/><path fill="#EA4335" d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.31 0 3.26 2.7 1.29 6.62l3.98 3.09c.95-2.85 3.6-4.96 6.73-4.96z"/></svg>Continue with Google</Button>
        <Button className="lovable-auth-button w-full" onClick={async () => { const r = await lovable.auth.signInWithOAuth("lovable", { redirect_uri: window.location.origin }); if (r.error) setError(r.error.message); }}>Continue with Lovable</Button>
      </div> : <>
        <Button variant="link" onClick={() => supabase.auth.signOut()}>Sign out</Button>
        <label className="block">Training logs<textarea aria-label="Training logs" rows={7} maxLength={100000} value={logs} onChange={(e) => setLogs(e.target.value)} /></label>
        <input type="file" aria-label="Upload training logs" accept=".txt,.log,.json" onChange={async (e) => { const f = e.target.files?.[0]; if (!f) return; if (f.size > 100000) { setError("Log file is too large (100 KB maximum)."); return; } setLogs(await f.text()); }} />
        <label className="block">Evaluation metrics (JSON)<textarea aria-label="Evaluation metrics" rows={5} maxLength={50000} value={metrics} onChange={(e) => setMetrics(e.target.value)} /></label>
        <p className="text-sm text-muted-foreground">Only the logs and metrics you submit leave your PC. Remove secrets and personal data first. AI usage is billed in credits.</p>
        <div className="flex gap-2"><Button disabled={busy || !logs.trim()} onClick={diagnose}><FlaskConical />{busy ? "Diagnosing…" : "Diagnose training"}</Button>{busy && <Button variant="outline" onClick={() => controller.current?.abort()}><Square />Stop</Button>}</div>
      </>}
      {error && <p role="alert" className="text-destructive break-words">{error}</p>}
      {answer && <div aria-label="AI diagnosis result" className="whitespace-pre-wrap break-words border-t border-border pt-4">{answer}</div>}
      {history.length > 0 && <div className="space-y-3 border-t border-border pt-4"><h3>Previous reviews</h3>{history.map((h) => <details key={h.id}><summary>{new Date(h.created_at).toLocaleString()} · {h.status}</summary><p className="whitespace-pre-wrap break-words">{h.diagnosis || "No diagnosis recorded."}</p></details>)}</div>}
    </section>
  </aside>, document.body);
}