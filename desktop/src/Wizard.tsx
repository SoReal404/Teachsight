import { useState } from "react";
import { TYPES, UNSURE, buildSteps, resolveUnsure, READY, Q } from "./questions";

const Icon = ({ d }: { d: string }) => <svg width="34" height="34" viewBox="0 0 32 32" fill="none" stroke="#4FD1B5" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={d} /></svg>;
const filled = (v: any) => (Array.isArray(v) ? v.length > 0 : String(v ?? "").trim().length > 0);

function Tags({ q, value, onChange }: { q: Q; value: string; onChange: (v: string) => void }) {
  const [t, setT] = useState("");
  const items = value ? value.split(",").filter(Boolean) : [];
  const add = () => { const x = t.trim().replace(/,/g, ""); if (x && !items.includes(x)) onChange([...items, x].join(",")); setT(""); };
  return (
    <div className="col">
      <div className="rw wr">{items.map((x) => <button key={x} className="opt sel" onClick={() => onChange(items.filter((y) => y !== x).join(","))}>{x} &times;</button>)}</div>
      <input aria-label={q.label} value={t} placeholder={q.placeholder} onChange={(e) => setT(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === ",") { e.preventDefault(); add(); } }} onBlur={add} />
    </div>
  );
}

function Question({ q, a, set }: { q: Q; a: Record<string, any>; set: (id: string, v: any) => void }) {
  const v = a[q.id];
  return (
    <div className="hv cd col" tabIndex={0} style={{ gap: 12 }}>
      <b className="qt">{q.label}{q.required ? " *" : ""}</b>
      {q.kind === "text" && <input aria-label={q.label} value={v ?? ""} placeholder={q.placeholder} onChange={(e) => set(q.id, e.target.value)} />}
      {q.kind === "long" && <textarea aria-label={q.label} rows={3} value={v ?? ""} placeholder={q.placeholder} onChange={(e) => set(q.id, e.target.value)} />}
      {q.kind === "tags" && <Tags q={q} value={v ?? ""} onChange={(x) => set(q.id, x)} />}
      {(q.kind === "choice" || q.kind === "multi") && (
        <div className="rw wr" style={{ gap: 8 }}>{q.options!.map((o) => {
          const on = q.kind === "multi" ? (v ?? []).includes(o.v) : v === o.v;
          return <button key={o.v} className={"opt" + (on ? " sel" : "")} aria-pressed={on} onClick={() => set(q.id, q.kind === "multi" ? (on ? (v as string[]).filter((x) => x !== o.v) : [...(v ?? []), o.v]) : o.v)}>{o.l}</button>;
        })}</div>)}
      <span className="more"><b style={{ color: "#4FD1B5" }}>Why I ask: </b>{q.why}</span>
    </div>
  );
}

export default function Wizard({ onCancel, onCreate }: { onCancel: () => void; onCreate: (name: string, brief: any) => Promise<void> }) {
  const [stage, setStage] = useState<"pick" | "unsure" | "steps">("pick");
  const [type, setType] = useState("");
  const [i, setI] = useState(0);
  const [a, setA] = useState<Record<string, any>>({});
  const [busy, setBusy] = useState(false);
  const set = (id: string, v: any) => setA((x) => ({ ...x, [id]: v }));
  const steps = type ? buildSteps(type) : [];
  const typeName = TYPES.find((t) => t.id === type)?.name ?? "";

  if (stage === "pick") return (
    <div className="page wide">
      <div className="rw sb"><div><h1>What do you want to build?</h1><p className="sub">Pick the closest one. Hover a card to see an example.</p></div><button className="btn" onClick={onCancel}>Cancel</button></div>
      <div className="g4">{TYPES.map((t, k) => {
        const ready = READY.has(t.id);
        return (
          <button key={t.id} className="hv cd tcard" style={{ animationDelay: `${k * 40}ms`, ...(k === 0 ? { borderColor: "#4FD1B5" } : {}), ...(t.id === "unsure" ? { borderStyle: "dashed" } : {}) }}
            onClick={() => { if (t.id === "unsure") { setStage("unsure"); } else { setType(t.id); setStage("steps"); setI(0); } }}>
            <span className="rw sb"><Icon d={t.icon} /><span className={"ch2 " + (t.id === "unsure" ? "bl" : ready ? "ok" : "gr")}>{t.id === "unsure" ? "Guided" : ready ? "Ready" : "Coming soon"}</span></span>
            <b className="qt" style={{ marginTop: 6 }}>{t.name}</b><span className="mu sm">{t.tech}</span>
            <span className="more">{t.example}</span>
          </button>);
      })}</div>
      <p className="mu sm">Types marked Coming soon are not built yet. You can answer their questions now and I will keep your answers.</p>
    </div>);

  if (stage === "unsure") return (
    <div className="page wide">
      <div><h1>Let’s find the right type</h1><p className="sub">Two quick questions.</p></div>
      <div className="g2">{UNSURE.map((q) => <Question key={q.id} q={q} a={a} set={set} />)}</div>
      <div className="rw sb"><button className="btn" onClick={() => setStage("pick")}>Back</button>
        <button className="btn p" disabled={!a.u_where || !a.u_other} onClick={() => { setType(resolveUnsure(a)); setStage("steps"); setI(0); }}>Next</button></div>
    </div>);

  const st = steps[i], last = i === steps.length - 1;
  const ok = st.qs.every((q) => !q.required || filled(a[q.id]));
  return (
    <div className="page wide">
      <div className="rw"><span className="ch2 ok">{typeName}</span><button className="btn sm ghost" onClick={() => { setStage("pick"); setType(""); }}>Change type</button>
        <span className="mu" style={{ marginLeft: "auto" }}>Step {i + 2} of {steps.length + 1}</span><span className="bar" style={{ width: 160 }}><i style={{ width: `${((i + 2) / (steps.length + 1)) * 100}%` }} /></span></div>
      <div><h1>{st.title}</h1><p className="sub">{st.sub}</p></div>
      <div className={st.qs.length > 2 ? "g2" : "g1"}>{st.qs.map((q) => <Question key={q.id} q={q} a={a} set={set} />)}</div>
      <div className="rw sb"><button className="btn" onClick={() => (i === 0 ? setStage("pick") : setI(i - 1))}>Back</button>
        <button className="btn p" disabled={!ok || busy} onClick={async () => { if (!last) return setI(i + 1); setBusy(true); await onCreate(String(a.name).trim(), { ...a, type }); setBusy(false); }}>{last ? "Create project" : "Next"}</button></div>
    </div>);
}
