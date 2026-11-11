import { useState } from "react";
import { engine } from "./engine";

export const ROLE_NAME: Record<string, string> = { train: "Training", val: "Validation", test: "Final exam", ignore: "Ignore" };
const ROLE_COL: Record<string, string> = { train: "#4FD1B5", val: "#B79CFF", test: "#7FB4FF", ignore: "#F2B84B" };
const ROLE_CLS: Record<string, string> = { train: "ok", val: "vi", test: "bl", ignore: "am" };
const NEXT: Record<string, string> = { train: "test", test: "val", val: "ignore", ignore: "train" };
const LEFT: [string, string][] = [["Settings", "Your answers and choices for this project."], ["Labels", "Category names and any boxes or outlines."], ["Training runs", "Every try, with its settings and score."], ["Exports", "The trained model and the shareable test page."]];
const W = 1120;

export default function MindMap({ pid, name, root, folders, crossDup, onRole }: { pid: string; name: string; root: string; folders: any[]; crossDup: number; onRole: (folder: string, role: string) => void }) {
  const [all, setAll] = useState(false);
  const shown = all ? folders : folders.slice(0, 4), hidden = folders.length - shown.length;
  const rows = shown.length + (hidden > 0 ? 1 : 0), RH = 128, H = Math.max(420, rows * RH + 24), cy = H / 2;
  const ry = (i: number) => (H - rows * RH) / 2 + RH * i + RH / 2, ly = (i: number) => cy + (i - 1.5) * 96;
  const P = (d: string, c: string, k: string) => <path key={k} d={d} stroke={c} strokeWidth={3} fill="none" strokeLinecap="round" />;
  return (
    <div style={{ overflowX: "auto" }}>
      <div className="mm" style={{ height: H, width: W }}>
        <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ position: "absolute", left: 0, top: 0 }} aria-hidden="true">
          {LEFT.map((_, i) => P(`M210 ${cy} C 190 ${cy}, 190 ${ly(i)}, 170 ${ly(i)}`, "#3A424A", "l" + i))}
          {P(`M380 ${cy}H330`, "#3A424A", "cl")}{P(`M560 ${cy}H610`, "#4FD1B5", "cr")}
          {shown.map((f, i) => P(`M730 ${cy} C 755 ${cy}, 755 ${ry(i)}, 780 ${ry(i)}`, ROLE_COL[f.role] ?? "#3A424A", "r" + i))}
        </svg>
        {LEFT.map(([t, tip], i) => <div key={t} className="hv nd nb" tabIndex={0} style={{ left: 0, top: ly(i) - 26, width: 170, height: 52, display: "flex", alignItems: "center" }}><b>{t}</b><span className="pop" style={{ left: "100%", marginLeft: 14, top: 0, width: 240 }}>{tip}</span></div>)}
        <div className="nd nb" style={{ left: 210, top: cy - 25, width: 120, height: 50, display: "flex", alignItems: "center", justifyContent: "center" }}><b>In the app</b></div>
        <div className="nd" style={{ left: 380, top: cy - 50, width: 180, height: 100, background: "#12352D", border: "2px solid #4FD1B5", borderRadius: 24, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "0 10px", textAlign: "center" }}><b style={{ fontSize: 20, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 160 }}>{name}</b><span className="mu sm">Your project</span></div>
        <div className="nd nb" style={{ left: 610, top: cy - 25, width: 120, height: 50, display: "flex", alignItems: "center", justifyContent: "center" }}><b>Your data</b></div>
        {shown.map((f, i) => {
          const pics: string[] = [...Object.values<string[]>(f.samples ?? {}).flatMap((s) => s.slice(0, 2)), ...(f.loose_samples ?? [])].slice(0, 4);
          const cls = Object.entries<number>(f.classes ?? {}).map(([k, v]) => `${k} ${v.toLocaleString()}`).join(" · ");
          return (
            <div key={f.name} className="hv nd nb" tabIndex={0} style={{ left: 780, top: ry(i) - 54, width: 340, height: 108, borderColor: ROLE_COL[f.role] }}>
              <div className="rw sb"><b style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.name}</b>
                <button className={"ch2 " + ROLE_CLS[f.role]} style={{ border: 0, cursor: "pointer", minHeight: 44, padding: "5px 14px" }} aria-label={`${f.name} is used as ${ROLE_NAME[f.role]}. Click to change.`} onClick={() => onRole(f.name, NEXT[f.role])}>{ROLE_NAME[f.role]} &#9662;</button></div>
              <div className="mu sm">{f.count.toLocaleString()} pictures{cls ? ` · ${cls}` : " · no category folders inside"}</div>
              {crossDup > 0 && f.role !== "ignore" && <span className="ch2 am" style={{ fontSize: 13, marginTop: 4 }}>copies in more than one folder</span>}
              <div className="pop" style={{ right: "100%", marginRight: 30, top: 0, width: 300 }}>
                <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>{pics.map((s) => <img key={s} className="ti" src={engine.thumb(pid, s, 112)} alt="" width={56} height={56} />)}</div>
                {f.role === "train" ? "Used to teach the AI." : f.role === "test" ? "Kept secret from the AI, then used to grade it fairly." : f.role === "val" ? "Used to check progress while the AI learns." : "Not used. Click the role to change it."}
              </div>
            </div>);
        })}
        {hidden > 0 && <button className="nd nb btn" style={{ left: 780, top: ry(shown.length) - 30, width: 340, height: 60 }} onClick={() => setAll(true)}>+ {hidden} more folders</button>}
      </div>
      <div className="mu sm" style={{ marginTop: 8 }}>{root}</div>
    </div>);
}
