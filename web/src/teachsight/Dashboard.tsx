import { TYPES } from "./questions";
const STAGE: Record<string, string> = { new: "Waiting for pictures", data: "Pictures added", checked: "Pictures checked", planned: "Plan ready", training: "Training", trained: "Trained", ready: "Ready-made model" };

export default function Dashboard({ projects, offline, onOpen, onNew, onDelete, onRetry }: { projects: any[]; offline: boolean; onOpen: (id: string) => void; onNew: () => void; onDelete: (p: any) => void; onRetry: () => void }) {
  return (
    <div className="page wide">
      <div className="rw sb"><div><h1>Your projects</h1><p className="sub">Pick up where you left off, or start something new.</p></div><button className="btn p" onClick={onNew}>+ New project</button></div>
      {offline && <div className="cd col"><b>I can’t reach the engine yet.</b><span className="mu">Is it running on port 8765? Start it, then try again.</span><div><button className="btn" onClick={onRetry}>Try again</button></div></div>}
      <div className="grid">
        <button className="pcard add" onClick={onNew}><span style={{ fontSize: 34 }}>+</span>New project</button>
        {projects.map((p) => (
          <div key={p.id} className="pcard" role="button" tabIndex={0} onClick={() => onOpen(p.id)} onKeyDown={(e) => e.key === "Enter" && onOpen(p.id)}>
            <b className="qt">{p.name}</b>
            <span className="mu goal">{p.goal || "No description"}</span>
            <div className="rw wr"><span className={"ch2 " + (p.stage === "trained" ? "ok" : "gr")}>{STAGE[p.stage] ?? p.stage}</span>{p.type && <span className="ch2 bl">{TYPES.find((t) => t.id === p.type)?.tech ?? p.type}</span>}{p.best_accuracy != null && <span>{Math.round(p.best_accuracy * 100)}% accurate</span>}</div>
            <div className="rw sb"><span className="mu sm">{new Date(p.updated * 1000).toLocaleDateString()}</span><button className="link" onClick={(e) => { e.stopPropagation(); onDelete(p); }}>Delete</button></div>
          </div>))}
      </div>
      {!offline && projects.length === 0 && <p className="mu">No projects yet. Create your first one and I’ll ask a few questions about what you want to build.</p>}
    </div>);
}
