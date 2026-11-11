import { useEffect, useRef, useState } from "react";
import { engine } from "./engine";

export default function AskAI({
  pid,
  initial,
  onClose,
  onChanged,
  onSettings,
}: {
  pid: string;
  initial: string;
  onClose: () => void;
  onChanged: () => void;
  onSettings: () => void;
}) {
  const [msgs, setMsgs] = useState<{ role: string; content: string; mode?: string; error?: string }[]>([]);
  const [input, setInput] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<"plan" | "code">(() => {
    const saved = localStorage.getItem(`teachsight_ai_mode_${pid}`);
    return saved === "plan" ? "plan" : "code"; // Default to code mode for full permissions
  });
  const [modelInfo, setModelInfo] = useState<any>(null);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    engine.project(pid).then((d) => {
      setMsgs(d.chat || []);
      if (d.state?.mode && ["plan", "code"].includes(d.state.mode)) {
        // Keep in sync with backend state if present
        setMode(d.state.mode);
      }
    }).catch(() => {});

    engine.modelInfo(pid).then(setModelInfo).catch(() => {});
  }, [pid]);

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, busy]);

  const switchMode = (m: "plan" | "code") => {
    setMode(m);
    localStorage.setItem(`teachsight_ai_mode_${pid}`, m);
  };

  async function send(textToSend?: string) {
    const t = (textToSend ?? input).trim();
    if (!t || busy) return;
    setBusy(true);
    if (!textToSend) setInput("");
    setMsgs((m) => [...m, { role: "user", content: t, mode }]);
    try {
      const r = await engine.talk(pid, t, mode);
      setMsgs((m) => [...m, { role: "assistant", content: r.reply, mode }]);
      onChanged();
      // refresh model info if a model was trained
      engine.modelInfo(pid).then(setModelInfo).catch(() => {});
    } catch (e: any) {
      setMsgs((m) => [...m, { role: "assistant", content: e.message, error: e.code, mode }]);
    }
    setBusy(false);
  }

  const quickPrompts = [
    "Where is the trained model file and scripts?",
    "How do I integrate this model into my website?",
    "Show me the predict.py inference code",
    "Open the model folder in File Explorer",
  ];

  return (
    <aside className="drawer" aria-label="Ask the AI">
      <div className="rw sb" style={{ alignItems: "center", borderBottom: "1px solid #2a3036", paddingBottom: 12 }}>
        <b className="qt" style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span>Ask AI</span>
          <span className={"ch2 sm " + (mode === "code" ? "ok" : "bl")} style={{ fontSize: 12, padding: "2px 8px" }}>
            {mode === "code" ? "⚡ Code Mode (Full Access)" : "📋 Plan Mode"}
          </span>
        </b>
        <button className="btn sm ghost" onClick={onClose} title="Close drawer">✕</button>
      </div>

      {/* Mode toggle */}
      <div className="col" style={{ gap: 6, background: "#111417", padding: "10px 12px", borderRadius: 14, border: "1px solid #23282e" }}>
        <div className="rw sb" style={{ alignItems: "center" }}>
          <span className="sm mu">Assistant Mode:</span>
          <div className="seg" style={{ margin: 0 }}>
            <span className={mode === "plan" ? "on" : ""} onClick={() => switchMode("plan")} title="Plan and advise on dataset & architecture">
              📋 Plan
            </span>
            <span className={mode === "code" ? "on" : ""} onClick={() => switchMode("code")} title="Full access: modify code, hyperparameters, retrain, export">
              ⚡ Code
            </span>
          </div>
        </div>
        <div className="sm" style={{ color: mode === "code" ? "#4fd1b5" : "#a4acb3", fontSize: 12 }}>
          {mode === "code"
            ? "✓ Full Permissions: view & edit code, retrain, inspect weights, export to websites."
            : "Guiding & planning: dataset advice, explanations, pre-flight recommendations."}
        </div>
      </div>

      {/* Quick Model info bar if trained */}
      {modelInfo?.has_model && (
        <div style={{ background: "#16201e", border: "1px solid #264e43", borderRadius: 12, padding: "8px 12px", fontSize: 13 }}>
          <div className="rw sb">
            <span style={{ color: "#4fd1b5", fontWeight: 600 }}>Model Ready: {modelInfo.config?.model || "Trained"}</span>
            <button
              className="btn sm"
              style={{ minHeight: 28, padding: "2px 10px", fontSize: 12 }}
              onClick={() => engine.openModelFolder(pid)}
            >
              📁 Open Folder
            </button>
          </div>
          <div className="mu trunc sm" style={{ marginTop: 4 }} title={modelInfo.path}>
            {modelInfo.path}
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="msgs">
        {msgs.length === 0 && (
          <div className="col" style={{ gap: 14, padding: "10px 0" }}>
            <p className="mu" style={{ margin: 0 }}>
              Ask about your pictures, retraining, your model files, or how to connect the model to a website or backend API.
            </p>
            <div className="col" style={{ gap: 8 }}>
              <span className="sm lb mu">Suggested Questions:</span>
              {quickPrompts.map((q) => (
                <button
                  key={q}
                  className="btn sm"
                  style={{ textAlign: "left", fontSize: 13, background: "#1c2025", padding: "8px 12px", minHeight: 36 }}
                  onClick={() => send(q)}
                >
                  💡 {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {msgs.map((m, i) => (
          <div key={i} className={"bubble " + (m.role === "user" ? "user" : "")}>
            {m.mode && (
              <div style={{ fontSize: 11, opacity: 0.6, marginBottom: 4, textTransform: "uppercase" }}>
                {m.mode === "code" ? "⚡ Code Mode" : "📋 Plan Mode"}
              </div>
            )}
            <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.5, wordBreak: "break-word" }}>
              {m.content}
            </div>

            {/* If message mentions model files, provide direct action buttons */}
            {m.role === "assistant" && (m.content.toLowerCase().includes("best.pt") || m.content.toLowerCase().includes("serve.py") || m.content.toLowerCase().includes("folder")) && (
              <div className="rw wr" style={{ marginTop: 10, gap: 8 }}>
                <button className="btn sm" style={{ minHeight: 32, padding: "4px 10px", fontSize: 12 }} onClick={() => engine.openModelFolder(pid)}>
                  📁 Open Folder in Explorer
                </button>
                <a
                  className="btn sm"
                  style={{ minHeight: 32, padding: "4px 10px", fontSize: 12, textDecoration: "none", display: "inline-flex", alignItems: "center" }}
                  href={engine.exportZipUrl(pid)}
                  download
                >
                  📦 Download Model ZIP
                </a>
              </div>
            )}

            {m.error?.startsWith("no_") || m.error === "bad_key" ? (
              <div style={{ marginTop: 8 }}>
                <button className="btn sm p" onClick={onSettings}>Open Settings</button>
              </div>
            ) : null}
          </div>
        ))}
        {busy && <div className="mu sm" style={{ fontStyle: "italic" }}>AI is thinking & analyzing project...</div>}
        <div ref={end} />
      </div>

      {/* Input */}
      <div className="rw" style={{ gap: 8 }}>
        <input
          aria-label="Your question"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
          placeholder={mode === "code" ? "Ask anything (code, deploy, retrain, files)..." : "Ask about planning or dataset..."}
        />
        <button className="btn p" disabled={busy || !input.trim()} onClick={() => send()}>
          Send
        </button>
      </div>
    </aside>
  );
}
