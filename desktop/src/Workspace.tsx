import { useCallback, useEffect, useRef, useState } from "react";
import { engine } from "./engine";
import { TYPES, READY, allQ, labelOf } from "./questions";
import MindMap from "./MindMap";
import Advanced from "./Advanced";
import AskAI from "./AskAI";

const NAMES = ["Data", "Check", "Plan", "Train", "Test", "Improve"];
const MODEL: Record<string, string> = { resnet18: "Quick and reliable", resnet50: "Larger and more accurate", mobilenet_v3_large: "Small and fast", ssdlite_mobilenet_v3: "Finds and boxes objects" };
const STEP_TIP: Record<string, string> = {
  "Checking data": "Looks at every picture and makes sure it can be read.",
  "Preparing images": "Resizes and mixes the pictures.",
  "Choosing model": "Picks the AI and times a few steps on your PC.",
  Training: "The AI studies your pictures again and again and gets a little better each round.",
  Evaluating: "Grades the AI on pictures it has never studied.",
  Exporting: "Saves your model, README.md, predict.py CLI, and serve.py web API.",
};
const fmt = (n: number) => n.toLocaleString();
const pct = (n: number) => `${Math.round(n * 100)}%`;
const toB64 = (f: File) => new Promise<string>((res, rej) => {
  const r = new FileReader();
  r.onload = () => res(String(r.result));
  r.onerror = () => rej(new Error("Could not read the file"));
  r.readAsDataURL(f);
});

function Chapter({ n, label, title, sub, innerRef, children }: { n: number; label: string; title: string; sub?: string; innerRef: (el: HTMLElement | null) => void; children: any }) {
  return (
    <section className="chapter" ref={innerRef}>
      <div className="bn" aria-hidden="true">{n}</div>
      <div className="rise" style={{ position: "relative", zIndex: 1 }}><div className="lb">{n} · {label}</div><h1>{title}</h1>{sub && <p className="sub">{sub}</p>}</div>
      {children}
    </section>
  );
}

function Bar({ label, value, max, text, color, tip }: { label: string; value: number; max: number; text: string; color?: string; tip?: string }) {
  return (
    <div className="hv rw" tabIndex={0} style={{ padding: "6px 0" }}>
      <span style={{ width: 110, overflow: "hidden", textOverflow: "ellipsis" }}>{label}</span>
      <span className="bar" style={{ flex: 1, width: "auto" }}><i style={{ width: `${(value / Math.max(max, 1)) * 100}%`, background: color }} /></span>
      <b style={{ width: 70, textAlign: "right" }}>{text}</b>
      {tip && <span className="pop" style={{ right: 80, top: -64, width: 300 }}>{tip}</span>}
    </div>
  );
}

function Ring({ value }: { value: number }) {
  return (
    <svg width="170" height="170" viewBox="0 0 180 180" role="img" aria-label={`${pct(value)} correct`}>
      <circle cx="90" cy="90" r="70" fill="none" stroke="#2A3036" strokeWidth="16" />
      <circle cx="90" cy="90" r="70" fill="none" stroke="#4FD1B5" strokeWidth="16" strokeLinecap="round" strokeDasharray={`${439.8 * value} 439.8`} transform="rotate(-90 90 90)" />
      <text x="90" y="101" textAnchor="middle" fontSize="40" fontWeight="700" fill="#EEF1F3">{pct(value)}</text>
    </svg>
  );
}

function ModelExportCard({ pid, runId, path }: { pid: string; runId?: string; path?: string }) {
  const [copied, setCopied] = useState(false);
  const [showCode, setShowCode] = useState(false);

  const copyPath = () => {
    if (!path) return;
    navigator.clipboard?.writeText(path);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  return (
    <div className="cd col rise export-card" style={{ gap: 14 }}>
      <div className="rw sb wr">
        <div className="rw" style={{ gap: 12 }}>
          <span style={{ fontSize: 32 }}>📦</span>
          <div className="col" style={{ gap: 2 }}>
            <div className="rw" style={{ gap: 8 }}>
              <b className="qt" style={{ color: "#4fd1b5" }}>Trained Model & Developer Assets</b>
              <span className="ch2 ok sm">Ready for Deployment</span>
            </div>
            <span className="mu sm">
              Everything needed to run inference, deploy to websites, or continue development.
            </span>
          </div>
        </div>
        <div className="rw wr" style={{ gap: 8 }}>
          <button className="btn sm p" onClick={() => engine.openModelFolder(pid)}>
            📁 Open Folder in Explorer
          </button>
          <a
            className="btn sm"
            href={engine.exportZipUrl(pid, runId)}
            download
            style={{ textDecoration: "none" }}
          >
            ⬇ Download ZIP Bundle
          </a>
          <button className="btn sm ghost" onClick={() => setShowCode(!showCode)}>
            {showCode ? "Hide Integration Code" : "🌐 Website & Python Code"}
          </button>
        </div>
      </div>

      {path && (
        <div className="rw sb" style={{ background: "#101214", padding: "8px 14px", borderRadius: 10, border: "1px solid #23282e" }}>
          <div className="rw trunc" style={{ gap: 8, flex: 1 }}>
            <span className="mu sm" style={{ flex: "none" }}>Folder Location:</span>
            <code className="sm trunc" style={{ color: "#7fb4ff" }} title={path}>{path}</code>
          </div>
          <button className="btn sm ghost" style={{ minHeight: 28, padding: "2px 10px", fontSize: 12, flex: "none" }} onClick={copyPath}>
            {copied ? "✓ Copied!" : "📋 Copy Path"}
          </button>
        </div>
      )}

      <div className="col" style={{ gap: 6 }}>
        <span className="lb mu" style={{ fontSize: 11 }}>Package Contents:</span>
        <div className="rw wr" style={{ gap: 8 }}>
          <span className="file-badge">best.pt (weights)</span>
          <span className="file-badge">README.md (coder guide)</span>
          <span className="file-badge">predict.py (standalone CLI)</span>
          <span className="file-badge">serve.py (FastAPI web server)</span>
          <span className="file-badge">train.py (retraining)</span>
          <span className="file-badge">config.yaml</span>
          <span className="file-badge">labels.json</span>
          <span className="file-badge">requirements.txt</span>
        </div>
      </div>

      {showCode && (
        <div className="col rise" style={{ gap: 10, background: "#101214", padding: 16, borderRadius: 12, border: "1px solid #23282e", marginTop: 4 }}>
          <div className="rw sb">
            <b className="sm" style={{ color: "#4fd1b5" }}>1. Launch Local Web API Server (serve.py)</b>
            <span className="mu sm">Terminal</span>
          </div>
          <pre style={{ margin: 0, padding: 10, background: "#16191d", borderRadius: 8 }}>
            <code>cd "{path}"&#10;pip install -r requirements.txt&#10;python serve.py</code>
          </pre>
          <p className="mu sm" style={{ margin: "2px 0 6px" }}>
            This starts a REST API at <b style={{ color: "#fff" }}>http://localhost:8000</b> with interactive browser testing at <b style={{ color: "#fff" }}>http://localhost:8000</b> and Swagger docs at <b style={{ color: "#fff" }}>/docs</b>.
          </p>

          <div className="rw sb" style={{ marginTop: 6 }}>
            <b className="sm" style={{ color: "#4fd1b5" }}>2. Connect Any Website (JavaScript fetch)</b>
            <span className="mu sm">Frontend HTML / React / Vue</span>
          </div>
          <pre style={{ margin: 0, padding: 10, background: "#16191d", borderRadius: 8 }}>
            <code>{`// Send an image file to your model server
const formData = new FormData();
formData.append("file", fileInputElement.files[0]);

const response = await fetch("http://localhost:8000/predict", {
  method: "POST",
  body: formData
});
const data = await response.json();
console.log("Top prediction:", data.top);
console.log("All probabilities:", data.predictions);`}</code>
          </pre>

          <div className="rw sb" style={{ marginTop: 6 }}>
            <b className="sm" style={{ color: "#4fd1b5" }}>3. Run Single Image in Python CLI (predict.py)</b>
          </div>
          <pre style={{ margin: 0, padding: 10, background: "#16191d", borderRadius: 8 }}>
            <code>python predict.py "path/to/test_image.jpg"</code>
          </pre>
        </div>
      )}
    </div>
  );
}

export default function Workspace({
  pid,
  sidebarOpen,
  onToggleSidebar,
  onBack,
  onChanged,
  onSettings,
}: {
  pid: string;
  sidebarOpen?: boolean;
  onToggleSidebar?: () => void;
  onBack: () => void;
  onChanged: () => void;
  onSettings: () => void;
}) {
  const [p, setP] = useState<any>(null);
  const [job, setJob] = useState<any>(null);
  const [runs, setRuns] = useState<any[]>([]);
  const [mInfo, setMInfo] = useState<any>(null);
  const [diag, setDiag] = useState<any>(null);
  const [adv, setAdv] = useState(false);
  const [ask, setAsk] = useState<string | null>(null);
  const [path, setPath] = useState("");
  const [changing, setChanging] = useState(false);
  const [off, setOff] = useState(false);
  const [offText, setOffText] = useState("");
  const [addHelp, setAddHelp] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState("");
  const [active, setActive] = useState(0);
  const [progress, setProgress] = useState(0);
  const [pred, setPred] = useState<any>(null);
  const [toast, setToast] = useState("");
  const sc = useRef<HTMLDivElement>(null);
  const refs = useRef<(HTMLElement | null)[]>([]);
  const prevCount = useRef(0);
  const planning = useRef(false);
  const notify = useRef(true);

  const load = useCallback(async () => {
    const d = await engine.project(pid);
    setP(d);
    onChanged();
    return d;
  }, [pid]);

  const loadRuns = useCallback(async () => {
    const r = await engine.runs(pid).catch(() => []);
    setRuns(r);
    engine.modelInfo(pid).then(setMInfo).catch(() => {});
    return r;
  }, [pid]);

  useEffect(() => {
    let alive = true;
    (async () => {
      const d = await engine.project(pid).catch(() => null);
      if (!alive || !d) return;
      setP(d);
      setPath(d.state.data_dir ?? "");
      const r = await loadRuns();
      if (!alive) return;
      setRuns(r);
      if (d.state.job_id) {
        const j = await engine.job(d.state.job_id).catch(() => null);
        if (alive) setJob(j);
      }
    })();
    engine.settings().then((s) => { notify.current = s.notifications; }).catch(() => {});
    return () => { alive = false; };
  }, [pid]);

  useEffect(() => {
    if (!job || ["done", "failed", "cancelled"].includes(job.status)) return;
    const t = setInterval(async () => {
      const j = await engine.job(job.id);
      if (notify.current && "Notification" in window && Notification.permission === "granted") {
        if (j.status === "asking" && job.status !== "asking") new Notification("Your training needs a decision");
        if (j.status === "done") new Notification("Your model is ready");
      }
      setJob(j);
      if (["done", "failed", "cancelled"].includes(j.status)) {
        await loadRuns();
        await load();
      }
    }, 1500);
    return () => clearInterval(t);
  }, [job?.id, job?.status]);

  const st = p?.state ?? {}, brief = st.brief ?? {}, res = st.resolved, plan = st.plan;
  const confirmed = !!st.data_confirmed, checked = !!st.balance_choice && st.balance_choice !== "add_more";
  const metrics = job?.status === "done" ? job.result?.metrics : (runs.find((r) => r.metrics)?.metrics ?? null);
  const pretrained = !!st.pretrained;
  // What can be trained is decided by the pictures, not by the questionnaire.
  const canTrain = !!plan && (plan.task === "classification" || plan.task === "detection");
  const vis = [true, confirmed, checked && !!plan, !!job || runs.length > 0, !!metrics || pretrained, !!metrics || pretrained];
  const count = vis.filter(Boolean).length;

  useEffect(() => {
    if (confirmed && checked && !plan && !planning.current) {
      planning.current = true;
      engine.plan(pid).then(load).catch((e) => setErr(e.message)).finally(() => { planning.current = false; });
    }
  }, [confirmed, checked, plan]);

  useEffect(() => {
    if (metrics && job?.status !== "running") engine.diagnosis(pid).then(setDiag).catch(() => {});
  }, [metrics?.overall, job?.status]);

  useEffect(() => {
    if (!p) return;
    const el = refs.current[count - 1];
    if (el && prevCount.current !== count) el.scrollIntoView({ behavior: prevCount.current === 0 ? "auto" : "smooth", block: "start" });
    prevCount.current = count;
  }, [count, !!p]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(""), 3500);
    return () => clearTimeout(t);
  }, [toast]);

  const onScroll = () => {
    const s = sc.current;
    if (!s) return;
    let a = 0;
    refs.current.forEach((el, i) => { if (el && el.offsetTop - s.scrollTop <= s.clientHeight * 0.4) a = i; });
    setActive(a);
    setProgress(s.scrollTop / Math.max(1, s.scrollHeight - s.clientHeight));
  };

  const run = async (name: string, fn: () => Promise<any>) => {
    setBusy(name);
    setErr("");
    try { await fn(); await load(); } catch (e: any) { setErr(e.message); }
    setBusy("");
  };

  const go = (i: number) => refs.current[i]?.scrollIntoView({ behavior: "smooth", block: "start" });
  const ref = (i: number) => (el: HTMLElement | null) => { refs.current[i] = el; };

  async function tryPicture(f?: File) {
    if (!f) return;
    setErr("");
    try {
      const b64 = await toB64(f);
      const r = await engine.predict(pid, b64);
      setPred(r.detections ? { url: b64, b64, dets: r.detections, done: false } : { url: b64, b64, preds: r.predictions ?? [], done: false });
    } catch (e: any) {
      setErr(e.message);
    }
  }

  if (!p) return <div className="page"><p className="mu">Loading your project...</p></div>;

  const type = brief.type as string, tech = TYPES.find((t) => t.id === type)?.tech ?? "";
  const train = res?.folders?.find((f: any) => f.role === "train");
  const bal = st.balance, silent = !!st.balance_note, labels: string[] = res?.labels ?? [];
  const maxCount = Math.max(...Object.values<number>(res?.counts ?? { x: 1 }));
  const answers = allQ(type).filter((q) => q.id !== "name" && brief[q.id] && (!Array.isArray(brief[q.id]) || brief[q.id].length));
  const pdone = job?.status === "done" || (runs.length > 0 && !job);
  const running = job && ["running", "paused", "asking"].includes(job.status);
  const attempts = [...runs].reverse().filter((r) => r.metrics);

  return (
    <div className="ws">
      <header className="t">
        <div className="rw">
          <button className="btn sm" onClick={onBack}>&lsaquo; Projects</button>
          {onToggleSidebar && (
            <button
              className="btn sm ghost"
              onClick={onToggleSidebar}
              title={sidebarOpen ? "Hide left menu to get more space" : "Show left menu"}
              style={{ padding: "6px 12px" }}
            >
              {sidebarOpen ? "◀ Menu" : "☰ Menu"}
            </button>
          )}
          <b className="trunc">{p.meta.name}</b>
          {tech && <span className="ch2 bl">{tech}</span>}
        </div>
        <nav className="st" aria-label="Progress">
          {NAMES.map((n, i) => (
            <button
              key={n}
              disabled={!vis[i]}
              className={"sp" + (i === active && !adv ? " on" : vis[i] ? " dn" : "")}
              onClick={() => { setAdv(false); setTimeout(() => go(i), 0); }}
            >
              <i>{i + 1}</i>{n}
            </button>
          ))}
        </nav>
        <div className="rw">
          <button className="btn sm" onClick={() => setAsk("")}>
            Ask AI
          </button>
          <div className="seg">
            <span className={!adv ? "on" : ""} onClick={() => setAdv(false)}>Easy</span>
            <span className={adv ? "on" : ""} onClick={() => setAdv(true)}>Advanced</span>
          </div>
        </div>
      </header>

      <div className="pbw"><div className="pb" style={{ transform: `scaleX(${progress})` }} /></div>

      {adv ? (
        <div className="scroller"><Advanced pid={pid} /></div>
      ) : (
        <div className="scroller" ref={sc} onScroll={onScroll}>
          {/* 1 DATA */}
          <Chapter n={1} label="Data" title={res && !changing ? "Is this your data?" : "Where are your pictures?"} sub={res && !changing ? "I looked inside your folder. Tell me if I understood it." : "Paste the path of the folder that holds them."} innerRef={ref(0)}>
            {!res || changing ? (
              <div className="cd col rise">
                <b className="qt">Your folder</b>
                <span className="mu">It should contain one sub-folder for each category (cats, dogs), or training and test folders that each contain them. Tip: in File Explorer, hold Shift, right-click the folder and choose Copy as path.</span>
                <div className="rw">
                  <input
                    aria-label="Folder path"
                    value={path}
                    placeholder="C:\Pictures\Pets"
                    onChange={(e) => setPath(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && path && run("data", async () => { await engine.setData(pid, path); setChanging(false); })}
                  />
                  <button className="btn p" disabled={!path || busy === "data"} onClick={() => run("data", async () => { await engine.setData(pid, path); setChanging(false); })}>
                    {busy === "data" ? "Looking..." : "Check my folder"}
                  </button>
                </div>
                {err && <p className="warn">{err}</p>}
                {!pretrained && (
                  <div className="cd col" style={{ borderStyle: "dashed" }}>
                    <b className="qt">No pictures yet? Start with a ready-made model</b>
                    <span className="mu">
                      You can try the app right now with a model that already knows everyday objects and animals.
                      Add your own pictures later and train a model of your own.
                    </span>
                    <div>
                      <button className="btn" disabled={busy === "pretrained"} onClick={() => run("pretrained", async () => { await engine.usePretrained(pid); setChanging(false); })}>
                        {busy === "pretrained" ? "Getting it ready..." : "Use a ready-made model"}
                      </button>
                    </div>
                  </div>
                )}
                {answers.length > 0 && (
                  <details className="mu">
                    <summary>Your answers</summary>
                    {answers.map((q) => (
                      <p key={q.id} className="sm" style={{ margin: "6px 0 0" }}>
                        <b>{q.label}</b><br />{labelOf(q, brief[q.id])}
                      </p>
                    ))}
                  </details>
                )}
              </div>
            ) : (
              <>
                <div className="rise">
                  <MindMap
                    pid={pid}
                    name={p.meta.name}
                    root={st.scan.root}
                    folders={res.folders}
                    crossDup={st.scan.cross_split_duplicates}
                    onRole={(f, r) => run("roles", () => engine.setRoles(pid, { ...(st.roles ?? {}), [f]: r }))}
                  />
                </div>
                <div className="g2">
                  <div className="cd col rise">
                    <b className="qt">I found {labels.length} categories</b>
                    {train && Object.entries<number>(train.classes).map(([k, v]) => (
                      <div key={k}>
                        <div className="rw sb"><b>{k}</b><span className="ch2 ok">{fmt(v)} pictures</span></div>
                        <div className="rw" style={{ marginTop: 8 }}>
                          {(train.samples[k] ?? []).map((s: string) => (
                            <img key={s} className="ti" src={engine.thumb(pid, s, 112)} alt="" width={56} height={56} />
                          ))}
                        </div>
                      </div>
                    ))}
                    {res.test_dir && <span className="mu sm">Final exam: {fmt(res.total_test)} pictures the AI never studies.</span>}
                  </div>
                  <div className="cd col rise">
                    <b className="qt">What I noticed</b>
                    {st.notes?.length || st.scan.broken_count || st.scan.duplicate_count ? (
                      <>
                        {st.notes.map((n: string) => <p key={n} className="warn" style={{ margin: 0 }}>{n}</p>)}
                        {st.scan.broken_count > 0 && <p className="warn" style={{ margin: 0 }}>{st.scan.broken_count} pictures could not be opened and will be skipped.</p>}
                        {st.scan.duplicate_count > 0 && <p className="mu" style={{ margin: 0 }}>{st.scan.duplicate_count} pictures are exact copies of others.</p>}
                      </>
                    ) : (
                      <span className="ch2 ok" style={{ alignSelf: "flex-start" }}>Everything matches what you told me</span>
                    )}
                    <span className="mu sm">Click a colored role on a folder in the map to change what it is used for.</span>
                  </div>
                </div>
                {err && <p className="warn">{err}</p>}
                <div className="rw wr rise">
                  <button className="btn p" disabled={!!res.problems.length || busy === "confirm"} onClick={() => run("confirm", () => engine.confirm(pid))}>
                    {confirmed ? "Confirmed. Continue" : "Yes, that’s right"}
                  </button>
                  <button className="btn" onClick={() => setOff(!off)}>Something’s off</button>
                  <button className="btn ghost" onClick={() => setChanging(true)}>Choose another folder</button>
                </div>
                {off && (
                  <div className="cd col rise">
                    <span className="mu">Change a folder’s role in the map, choose another folder, or tell me what looks wrong:</span>
                    <div className="rw">
                      <input aria-label="Tell me what to fix" value={offText} onChange={(e) => setOffText(e.target.value)} placeholder="For example: the cats folder also has some dogs" />
                      <button className="btn" disabled={!offText} onClick={() => { setAsk(offText); setOff(false); }}>Tell the AI</button>
                    </div>
                  </div>
                )}
              </>
            )}
          </Chapter>

          {/* 2 CHECK */}
          {vis[1] && (
            <Chapter n={2} label="Check" title={silent || !bal?.options?.length ? "Your data looks good" : "Your categories are a little uneven"} sub={silent || !bal?.options?.length ? "Nothing needs your attention here." : "Pick how to handle it. I put the best option first."} innerRef={ref(1)}>
              <div className="cd col rise" style={{ gap: 2 }}>
                {labels.map((l) => (
                  <Bar key={l} label={l} value={res.counts[l]} max={maxCount} text={fmt(res.counts[l])} tip={!silent && bal?.options?.length && l === bal.largest ? bal.message : undefined} />
                ))}
              </div>
              {!silent && bal?.options?.length > 0 && (
                <div className="g3">
                  {bal.options.map((o: any) => (
                    <button key={o.id} className={"hv cd rise opc" + (st.balance_choice === o.id ? " chosen" : "")} onClick={() => run("choice", () => engine.choose(pid, o.id))}>
                      <span className="rw sb"><b className="qt">{o.label.replace(" (recommended)", "")}</b></span>
                      <span className={"ch2 " + (o.recommended ? "ok" : "gr")} style={{ alignSelf: "flex-start" }}>{st.balance_choice === o.id ? "Chosen" : o.recommended ? "Recommended" : "Option"}</span>
                      <span className="more">{o.effect}</span>
                    </button>
                  ))}
                </div>
              )}
              {st.balance_choice === "add_more" && (
                <div className="cd col rise">
                  <b>Take your time.</b>
                  <span className="mu">Add your pictures to the folder, then I will check it again.</span>
                  <div><button className="btn p" onClick={() => run("data", () => engine.setData(pid, st.data_dir))}>I added pictures: check again</button></div>
                </div>
              )}
            </Chapter>
          )}

          {/* 3 PLAN */}
          {vis[2] && (
            <Chapter n={3} label="Plan" title="Here’s the plan" sub="One click to start. Hover any card to see why." innerRef={ref(2)}>
              <div className="g4">
                {[
                  ["Pictures", fmt(plan.total_images), plan.val_images
                    ? `${fmt(plan.total_images - plan.exam_images - plan.val_images)} teach the AI, ${fmt(plan.val_images)} check it, ${fmt(plan.exam_images)} are the final exam.`
                    : `${fmt(plan.total_images - plan.exam_images)} teach the AI.${plan.exam_images ? ` ${fmt(plan.exam_images)} are the final exam.` : " I hold back some to check the AI."}`],
                  ["AI type", MODEL[plan.model] ?? plan.model, `Chosen because ${plan.model_note}.`],
                  ["Training", `${plan.epochs} rounds`, "Each round studies all your pictures once."],
                  ["Time", "Measured at start", `I time a few steps on your ${plan.device === "cuda" ? "graphics card" : "processor (slower)"}, then show a finish time.`]
                ].map(([l, v, tip]) => (
                  <button key={l} className="hv cd rise col" style={{ gap: 6 }}>
                    <span className="lb mu">{l}</span>
                    <b style={{ fontSize: 24 }}>{v}</b>
                    <span className="more">{tip}</span>
                  </button>
                ))}
              </div>
              {plan.notes?.length > 0 && (
                <div className="cd rise col" style={{ gap: 6 }}>
                  {plan.notes.map((n: string) => (
                    <p key={n} className="mu" style={{ margin: 0 }}>{n}</p>
                  ))}
                </div>
              )}
              {!canTrain && (
                <div className="cd rise">
                  <b>Training for “{tech}” is not ready yet.</b>
                  <span className="mu"> Your answers are saved, so it will be ready to go when it is.</span>
                </div>
              )}
              {err && <p className="warn">{err}</p>}
              <div className="rw rise">
                <button className="btn p big" disabled={!canTrain || !!running || busy === "start"} onClick={() => run("start", async () => { const r = await engine.approve(pid); setJob(r.job); })}>
                  Start training
                </button>
                <button className="btn" onClick={() => go(1)}>Change the plan</button>
              </div>
            </Chapter>
          )}

          {/* 4 TRAIN */}
          {vis[3] && (job || runs.length > 0) && (
            <Chapter
              n={4}
              label="Train"
              title={
                job?.status === "asking"
                  ? "I need a decision"
                  : pdone
                  ? "Training finished"
                  : job?.status === "failed"
                  ? "Something went wrong"
                  : job?.status === "cancelled"
                  ? "Training stopped"
                  : `Training: ${job?.overall_percent ?? 100}%`
              }
              sub={
                job?.eta_s && job.status === "running"
                  ? `Finishes around ${new Date(job.finish_at * 1000).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}. Hover a step to see what it is doing.`
                  : undefined
              }
              innerRef={ref(3)}
            >
              {job?.status === "asking" && job.question && (
                <div className="cd col rise" style={{ borderColor: "#F2B84B", borderWidth: 2 }}>
                  <b className="qt">{job.question.text}</b>
                  <div className="g3">
                    {job.question.options.map((o: any) => (
                      <button key={o.id} className={"btn" + (o.recommended ? " p" : "")} onClick={() => engine.answer(job.id, o.id)}>
                        {o.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {job?.status === "failed" && (
                <div className="cd col rise" style={{ borderColor: "#F2B84B", borderWidth: 2 }}>
                  <b className="qt">I could not finish this run</b>
                  <span className="mu">{job.error}</span>
                  <div className="rw">
                    <button className="btn p" onClick={() => run("start", async () => { const r = await engine.approve(pid); setJob(r.job); })}>
                      Try again
                    </button>
                    <button className="btn" onClick={() => setAsk(`My training failed with: ${job.error}`)}>
                      Ask the AI about it
                    </button>
                  </div>
                </div>
              )}

              {job && (
                <div className="cd col rise" style={{ gap: 4 }}>
                  {Object.entries<any>(job.steps).map(([n, s]) => (
                    <div key={n} className="hv" tabIndex={0}>
                      <div className="rw" style={{ padding: "6px 0" }}>
                        <span style={{ width: 150 }}>{n}</span>
                        <span className="bar" style={{ flex: 1, width: "auto" }}>
                          <i style={{ width: `${s.percent}%`, background: s.status === "running" && job.status !== "running" ? "#F2B84B" : undefined }} />
                        </span>
                        <span className={"ch2 " + (s.status === "done" ? "ok" : s.status === "running" ? "am" : "gr")} style={{ width: 80, textAlign: "center" }}>
                          {s.status === "running" ? `${Math.round(s.percent)}%` : s.status}
                        </span>
                      </div>
                      <span className="more" style={{ marginLeft: 164 }}>{STEP_TIP[n]}</span>
                    </div>
                  ))}
                </div>
              )}

              {job && ["running", "paused"].includes(job.status) && (
                <div className="rw rise">
                  <button className="btn" onClick={() => engine.control(job.id, job.status === "running" ? "pause" : "resume")}>
                    {job.status === "running" ? "Pause" : "Resume"}
                  </button>
                  <button className="btn ghost" onClick={() => engine.control(job.id, "cancel")}>
                    Cancel
                  </button>
                </div>
              )}
            </Chapter>
          )}

          {/* 5 TEST */}
          {vis[4] && (metrics || pretrained) && (
            <Chapter
              n={5}
              label="Test"
              title={pretrained ? "Try the ready-made model" : "Try it on a new picture"}
              sub={
                pretrained
                  ? "This model already knows everyday objects and animals. It is a good way to try the app before you add your own pictures."
                  : metrics?.metric_label
                  ? `Average precision at 0.5: ${Math.round(metrics.overall * 100)}%. That is how often a box lands on the right object.`
                  : `It got ${Math.round(metrics.overall * 100)} of 100 ${metrics.source === "exam" ? "exam" : "check"} pictures right.`
              }
              innerRef={ref(4)}
            >
              <div className="g2" style={{ gridTemplateColumns: "1fr 1.25fr" }}>
                {metrics ? (
                  <div className="cd rise rw" style={{ gap: 22 }}>
                    <Ring value={metrics.overall} />
                    <div className="col" style={{ flex: 1, gap: 8 }}>
                      {Object.entries<number>(metrics.per_class).map(([k, v]) => (
                        <Bar key={k} label={k} value={v} max={1} text={pct(v)} />
                      ))}
                      <span className="mu sm">{metrics.source === "exam" ? "Graded on your exam folder: pictures the AI never studied." : "Graded on pictures held back from training."}</span>
                    </div>
                  </div>
                ) : (
                  <div className="cd rise col" style={{ gap: 8 }}>
                    <b className="qt">A ready-made model is ready</b>
                    <span className="mu">
                      It knows {st.pretrained_task === "detection" ? "common objects" : "everyday objects and animals"} out of the box.
                      Add your own pictures and train to get a model of your own.
                    </span>
                  </div>
                )}
                <div className="cd rise col">
                  <b className="qt">Try it yourself</b>
                  <label className="drop" onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); tryPicture(e.dataTransfer.files[0]); }}>
                    {pred ? (
                      <div className="rw" style={{ gap: 18, alignItems: "flex-start" }}>
                        <div className="hv" tabIndex={0}>
                          <img src={pred.url} alt="Your picture" style={{ width: 200, height: 150, objectFit: "cover", borderRadius: 14 }} />
                          {!pred.dets && (
                            <div className="pop" style={{ left: 0, bottom: -10, width: 270 }}>
                              <div style={{ marginBottom: 8 }}>Wrong? Pick the right answer:</div>
                              <div className="rw wr" style={{ gap: 8 }}>
                                {labels.map((l) => (
                                  <button key={l} className="btn sm" onClick={async (e) => { e.preventDefault(); await engine.correct(pid, pred.b64, l); setToast("Saved. I will use it when we improve."); }}>
                                    {l}
                                  </button>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                        <div className="col" style={{ flex: 1, gap: 8 }}>
                          {pred.dets ? (
                            <>
                              <span className="lb mu">The AI found</span>
                              <div className="rw sb">
                                <b style={{ fontSize: 28 }}>{pred.dets.length} object{pred.dets.length === 1 ? "" : "s"}</b>
                              </div>
                              {pred.dets.slice(0, 8).map((d: any, i: number) => (
                                <Bar key={i} label={d.label} value={d.confidence} max={1} text={pct(d.confidence)} color={i ? "#6B747C" : undefined} />
                              ))}
                              <span className="mu sm">Each box shows where the object is, from left-top to right-bottom.</span>
                            </>
                          ) : (
                            <>
                              <span className="lb mu">The AI says</span>
                              <div className="rw sb">
                                <b style={{ fontSize: 28 }}>{pred.preds[0].label}</b>
                                <b style={{ fontSize: 28, color: "#4FD1B5" }}>{pct(pred.preds[0].probability)}</b>
                              </div>
                              {pred.preds.map((x: any, i: number) => (
                                <Bar key={x.label} label={x.label} value={x.probability} max={1} text={pct(x.probability)} color={i ? "#6B747C" : undefined} />
                              ))}
                              <span className="mu sm">Hover the picture to correct it.</span>
                            </>
                          )}
                        </div>
                      </div>
                    ) : (
                      <span className="mu">Drop a picture here, or click to choose one.</span>
                    )}
                    <input type="file" accept="image/*" hidden onChange={(e) => tryPicture(e.target.files?.[0])} />
                  </label>
                  {err && <p className="warn">{err}</p>}
                  {toast && <span className="ch2 ok" style={{ alignSelf: "flex-start" }}>{toast}</span>}
                </div>
              </div>

              {mInfo?.path && (
                <ModelExportCard pid={pid} runId={mInfo.run_id} path={mInfo.path} />
              )}
            </Chapter>
          )}

          {/* 6 IMPROVE */}
          {vis[5] && metrics && (
            <Chapter n={6} label="Improve" title={diag?.options?.length ? "Let’s make it better" : "How it is doing"} sub={diag?.headline ?? "Here is what I found."} innerRef={ref(5)}>
              <div className="g2" style={{ gridTemplateColumns: "1.2fr 1fr" }}>
                <div className="cd col rise">
                  <span className="lb mu">What is holding it back</span>
                  <div style={{ fontSize: 21, fontWeight: 600 }}>{diag?.headline}</div>
                  <div className="mu">{diag?.detail}</div>
                </div>
                <div className="cd col rise">
                  <span className="lb mu">Your attempts</span>
                  {attempts.map((r, i) => (
                    <Bar key={r.id} label={`Try ${i + 1}`} value={r.metrics.overall} max={1} text={pct(r.metrics.overall)} color={i === attempts.length - 1 ? undefined : "#6B747C"} />
                  ))}
                </div>
              </div>

              {diag?.options?.length > 0 && (
                <div className="g3">
                  {diag.options.map((o: any) => (
                    <button
                      key={o.id}
                      className={"hv cd rise opc" + (o.recommended ? " chosen" : "")}
                      disabled={!!running}
                      onClick={() => o.id === "add_pictures" ? setAddHelp(true) : run("improve", async () => { const j = await engine.improve(pid, o.id); setJob(j); })}
                    >
                      <b className="qt">{o.title}</b>
                      <span className={"ch2 " + (o.recommended ? "ok" : "gr")} style={{ alignSelf: "flex-start" }}>{o.tag}</span>
                      <span className="more">{o.effect}</span>
                    </button>
                  ))}
                </div>
              )}

              {addHelp && (
                <div className="cd col rise">
                  <b>Add pictures to your folder, then check again.</b>
                  <span className="mu">I will keep your earlier attempts so you can compare.</span>
                  <div>
                    <button className="btn p" onClick={() => { setAddHelp(false); setChanging(false); run("data", () => engine.setData(pid, st.data_dir)).then(() => go(0)); }}>
                      I added pictures: check my data again
                    </button>
                  </div>
                </div>
              )}
              {err && <p className="warn">{err}</p>}
            </Chapter>
          )}
        </div>
      )}

      {ask !== null && (
        <AskAI
          pid={pid}
          initial={ask}
          onClose={() => setAsk(null)}
          onChanged={load}
          onSettings={onSettings}
        />
      )}
    </div>
  );
}
