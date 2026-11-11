import { useEffect, useState } from "react";
import { engine } from "./engine";

export default function Advanced({ pid }: { pid: string }) {
  const [runs, setRuns] = useState<any[]>([]);
  const [rid, setRid] = useState("");
  const [files, setFiles] = useState<Record<string, string>>({});
  const [activeTab, setActiveTab] = useState<"config" | "train" | "predict" | "serve" | "readme">("config");
  const [cfg, setCfg] = useState("");
  const [msg, setMsg] = useState("");
  const [mInfo, setMInfo] = useState<any>(null);

  useEffect(() => {
    engine.runs(pid).then((r) => {
      setRuns(r);
      if (r[0]) setRid(r[0].id);
    });
    engine.modelInfo(pid).then(setMInfo).catch(() => {});
  }, [pid]);

  useEffect(() => {
    if (rid) {
      engine.runFiles(pid, rid).then((f) => {
        setFiles(f);
        setCfg(f["config.yaml"] ?? "");
      });
    }
  }, [rid]);

  if (!runs.length) {
    return (
      <div className="page">
        No runs yet. Train a model in Easy mode first, then its code and settings appear here.
      </div>
    );
  }

  return (
    <div className="page wide">
      <div className="rw sb wr">
        <div className="rw">
          <b>Run:</b>
          <select value={rid} onChange={(e) => setRid(e.target.value)} style={{ width: "auto" }}>
            {runs.map((r) => (
              <option key={r.id} value={r.id}>
                {r.id} {r.metrics ? `— accuracy ${Math.round(r.metrics.overall * 100)}%` : ""}
              </option>
            ))}
          </select>
        </div>

        <div className="rw">
          <button className="btn sm p" onClick={() => engine.openModelFolder(pid)}>
            📁 Open Folder in Explorer
          </button>
          <a
            className="btn sm"
            href={engine.exportZipUrl(pid, rid)}
            download
            style={{ textDecoration: "none" }}
          >
            ⬇ Download Model ZIP
          </a>
        </div>
      </div>

      {mInfo?.path && (
        <div className="rw sb" style={{ background: "#101214", padding: "8px 14px", borderRadius: 10, border: "1px solid #23282e" }}>
          <span className="sm mu">Folder Location:</span>
          <code className="sm" style={{ color: "#7fb4ff" }}>{mInfo.path}</code>
        </div>
      )}

      {/* File selector tabs */}
      <div className="seg" style={{ alignSelf: "flex-start" }}>
        <span className={activeTab === "config" ? "on" : ""} onClick={() => setActiveTab("config")}>
          config.yaml
        </span>
        <span className={activeTab === "train" ? "on" : ""} onClick={() => setActiveTab("train")}>
          train.py
        </span>
        <span className={activeTab === "predict" ? "on" : ""} onClick={() => setActiveTab("predict")}>
          predict.py (CLI)
        </span>
        <span className={activeTab === "serve" ? "on" : ""} onClick={() => setActiveTab("serve")}>
          serve.py (Web API)
        </span>
        <span className={activeTab === "readme" ? "on" : ""} onClick={() => setActiveTab("readme")}>
          README.md
        </span>
      </div>

      {activeTab === "config" && (
        <div className="card">
          <div className="rw sb">
            <b>config.yaml</b>
            <span className="mu sm">(Single source of truth: Easy mode and train.py both use it)</span>
          </div>
          <textarea
            value={cfg}
            onChange={(e) => setCfg(e.target.value)}
            rows={14}
            spellCheck={false}
          />
          <div className="rw">
            <button
              className="btn p"
              onClick={async () => {
                try {
                  await engine.rerun(pid, rid, cfg);
                  setMsg("Started a new run. Check Easy mode for progress.");
                } catch (e: any) {
                  setMsg(e.message);
                }
              }}
            >
              Run again with these settings
            </button>
            <span className="mu sm">{msg}</span>
          </div>
        </div>
      )}

      {activeTab === "train" && (
        <div className="card">
          <div className="rw sb">
            <b>train.py</b>
            <span className="mu sm">(Reproducible retraining script you can run standalone)</span>
          </div>
          <pre>{files["train.py"] || "Loading..."}</pre>
        </div>
      )}

      {activeTab === "predict" && (
        <div className="card">
          <div className="rw sb">
            <b>predict.py</b>
            <span className="mu sm">(Standalone inference script for command line & Python imports)</span>
          </div>
          <pre>{files["predict.py"] || "Loading..."}</pre>
        </div>
      )}

      {activeTab === "serve" && (
        <div className="card">
          <div className="rw sb">
            <b>serve.py</b>
            <span className="mu sm">(FastAPI REST API server with interactive HTML test demo at http://localhost:8000)</span>
          </div>
          <pre>{files["serve.py"] || "Loading..."}</pre>
        </div>
      )}

      {activeTab === "readme" && (
        <div className="card">
          <div className="rw sb">
            <b>README.md</b>
            <span className="mu sm">(Documentation for coders, API deployment, and website integration)</span>
          </div>
          <pre>{files["README.md"] || "Loading..."}</pre>
        </div>
      )}
    </div>
  );
}
