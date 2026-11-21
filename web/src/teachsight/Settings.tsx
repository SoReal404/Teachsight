import { useEffect, useState } from "react";
import { engine, getEngineUrl, setEngineUrl } from "./engine";

export default function Settings() {
  const [s, setS] = useState<any>(null);
  const [pkey, setPkey] = useState("");
  const [msg, setMsg] = useState("");
  const [ok, setOk] = useState(true);
  const [busy, setBusy] = useState(false);

  const [loadErr, setLoadErr] = useState("");
  const [url, setUrl] = useState(getEngineUrl);
  const loadSettings = () => { setLoadErr(""); engine.settings().then(setS).catch((e) => setLoadErr(e.message)); };
  useEffect(loadSettings, []);

  const engineBox = (
    <div className="cd col">
      <b>Engine address</b>
      <span className="mu sm">Where the Teachsight engine runs on your computer. Usually http://127.0.0.1:8765.</span>
      <div className="rw"><input value={url} onChange={(e) => setUrl(e.target.value)} /><button className="btn" onClick={() => { setEngineUrl(url); loadSettings(); }}>Save &amp; connect</button></div>
    </div>
  );
  if (!s) return <div className="page"><h1>Settings</h1>{engineBox}{loadErr ? <div className="cd col"><b>Couldn't load your settings.</b><span className="mu">{loadErr}</span><div><button className="btn" onClick={loadSettings}>Try again</button></div></div> : <p className="mu">Loading…</p>}</div>;

  const patch = async (p: any) => setS(await engine.saveSettings(p));
  const providers: any = s.providers ?? {};
  const cur: any = providers[s.provider];
  const say = (m: string, good = true) => { setMsg(m); setOk(good); };

  async function saveProviderKey() {
    setBusy(true);
    try {
      await engine.saveProviderKey(s.provider, pkey);
      setPkey("");
      say("Key saved. It is kept in the Windows keychain, not in a file.");
      setS(await engine.settings());
    } catch (e: any) {
      say(e.message, false);
    }
    setBusy(false);
  }

  async function testProviderKey() {
    setBusy(true);
    try {
      const r = await engine.testProviderKey(s.provider, pkey || undefined, s.custom_base_url || undefined);
      say(r.message, !!r.ok);
    } catch (e: any) {
      say(e.message, false);
    }
    setBusy(false);
  }

  async function removeProviderKey() {
    setBusy(true);
    try {
      await engine.removeProviderKey(s.provider);
      say("Key removed from this PC.");
      setS(await engine.settings());
    } catch (e: any) {
      say(e.message, false);
    }
    setBusy(false);
  }

  return (
    <div className="page">
      <h2>Settings</h2>
      {engineBox}

      {/* AI connection */}
      <div className="card">
        <b>AI connection</b>
        <p className="mu sm" style={{ margin: "4px 0 8px" }}>
          The AI helper only answers when you ask it something. Training your model never needs it, so you can leave it off.
        </p>
        <label className="row">
          <input
            type="radio"
            checked={s.ai_mode === "own_key"}
            onChange={() => patch({ ai_mode: "own_key" })}
          />{" "}
          Use my own AI key
        </label>
        <label className="row">
          <input
            type="radio"
            checked={s.ai_mode === "account"}
            onChange={() => patch({ ai_mode: "account" })}
          />{" "}
          Use my NoCode CV account (plan)
        </label>
        {s.ai_mode === "own_key" ? (
          <>
            <div className="col" style={{ gap: 6, marginTop: 10 }}>
              <b className="sm">Who should answer?</b>
              {Object.entries<any>(providers).map(([id, p]) => (
                <label className="row" key={id}>
                  <input
                    type="radio"
                    name="provider"
                    checked={s.provider === id}
                    onChange={() => { patch({ provider: id }); setPkey(""); setMsg(""); }}
                  />
                  <span>
                    {p.label}
                    {p.free_tier ? <span className="ch2 ok sm" style={{ marginLeft: 8 }}>Free tier</span> : null}
                    {p.has_key ? <span className="ch2 ok sm" style={{ marginLeft: 8 }}>Key saved</span> : null}
                  </span>
                </label>
              ))}
            </div>

            {cur && (
              <div className="col" style={{ gap: 8, marginTop: 8 }}>
                <div className="row">
                  <input
                    type="password"
                    placeholder={cur.key_placeholder}
                    value={pkey}
                    onChange={(e) => setPkey(e.target.value)}
                  />
                  <button className="btn p" disabled={!pkey || busy} onClick={saveProviderKey}>
                    Save key
                  </button>
                  <button className="btn" disabled={busy} onClick={testProviderKey}>
                    {busy ? "Checking..." : "Test key"}
                  </button>
                  {cur.has_key && (
                    <button className="btn" disabled={busy} onClick={removeProviderKey}>
                      Remove
                    </button>
                  )}
                </div>
                <span className="mu sm">{cur.key_help}</span>
                {cur.has_key && !pkey && (
                  <span className="mu sm">A key for {cur.label} is already saved on this PC. Paste a new one to replace it.</span>
                )}
              </div>
            )}

            <div className="col" style={{ gap: 6, marginTop: 10 }}>
              <b className="sm">Model</b>
              <input
                placeholder={cur?.default_model || "model name"}
                defaultValue={s.provider_model || cur?.default_model || ""}
                onBlur={(e) => patch({ provider_model: e.target.value })}
              />
              {s.provider === "custom" && (
                <input
                  placeholder="https://your-server.example/v1"
                  defaultValue={s.custom_base_url || ""}
                  onBlur={(e) => patch({ custom_base_url: e.target.value })}
                />
              )}
              <span className="mu sm">
                Leave it empty to use the default model. Stronger models are slower and cost more; small models are enough for simple jobs.
              </span>
            </div>

            <div className="col" style={{ gap: 6, marginTop: 10 }}>
              <b className="sm">Spending cap</b>
              <input
                placeholder="0 = no cap"
                defaultValue={s.spend_cap_usd ?? 0}
                onBlur={(e) => patch({ spend_cap_usd: Number(e.target.value) || 0 })}
              />
              <span className="mu sm">
                The AI stops asking for help once it reaches this amount, so a project never costs more than you expect.
              </span>
            </div>
          </>
        ) : (
          <>
            <input
              placeholder="Server address"
              defaultValue={s.proxy_url}
              onBlur={(e) => patch({ proxy_url: e.target.value })}
            />
            <input
              placeholder="License key"
              defaultValue={s.license_key}
              onBlur={(e) => patch({ license_key: e.target.value })}
            />
          </>
        )}
        {msg && <p className="mu sm" style={{ color: ok ? undefined : "#F2B84B" }}>{msg}</p>}
      </div>

      <div className="card">
        <b>Behaviour</b>
        <label className="row">
          <input
            type="checkbox"
            checked={s.autopilot}
            onChange={(e) => patch({ autopilot: e.target.checked })}
          />{" "}
          Always choose the recommended fix for me
        </label>
        <p className="mu sm">
          When on, small and medium problems with your pictures are fixed with
          the recommended option without asking. Serious problems still ask you.
          Every choice is saved in the run's report.
        </p>
        <label className="row">
          <input
            type="checkbox"
            checked={s.notifications}
            onChange={(e) => patch({ notifications: e.target.checked })}
          />{" "}
          Notify me when the AI needs a decision or finishes
        </label>
      </div>

      <div className="card">
        <b>Privacy</b>
        <p className="mu sm">
          Your pictures never leave this PC. Only the chat text and a short
          summary (folder name, category names and counts) go to the AI service.
        </p>
      </div>
    </div>
  );
}
