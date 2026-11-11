import { useEffect, useState } from "react";
import { engine } from "./engine";
import {
  AppearanceSettings,
  DEFAULT_APPEARANCE,
  loadAppearanceSettings,
  saveAppearanceSettings,
} from "./theme";

export default function Settings() {
  const [s, setS] = useState<any>(null);
  const [pkey, setPkey] = useState("");
  const [msg, setMsg] = useState("");
  const [ok, setOk] = useState(true);
  const [busy, setBusy] = useState(false);
  const [appearance, setAppearance] = useState<AppearanceSettings>(loadAppearanceSettings);

  useEffect(() => {
    engine.settings().then(setS);
  }, []);

  if (!s) return <div className="page">Loading...</div>;

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

  const updateAppearance = (updates: Partial<AppearanceSettings>) => {
    const updated = saveAppearanceSettings(updates);
    setAppearance(updated);
  };

  const resetAppearance = () => {
    const def = saveAppearanceSettings(DEFAULT_APPEARANCE);
    setAppearance(def);
  };

  return (
    <div className="page">
      <h2>Settings</h2>

      {/* Appearance & Shader Backgrounds */}
      <div className="card">
        <b>Appearance & Shader Backgrounds</b>
        <p className="mu sm" style={{ margin: 0 }}>
          Customize the interactive GPU background visuals, colors, and behavior across projects.
        </p>

        <label className="row" style={{ marginTop: 4 }}>
          <input
            type="checkbox"
            checked={appearance.trainingBackground}
            onChange={(e) => updateAppearance({ trainingBackground: e.target.checked })}
          />
          Show animated shader background in training steps (Workspace)
        </label>

        <div className="col" style={{ gap: 8, marginTop: 8 }}>
          <b className="sm">Shader Design:</b>
          <label className="row">
            <input
              type="radio"
              name="theme"
              checked={appearance.globalTheme === "auto"}
              onChange={() => updateAppearance({ globalTheme: "auto" })}
            />
            <span><b>Auto / Random per project</b> (Each project gets a unique design that never changes when you reopen)</span>
          </label>
          <label className="row">
            <input
              type="radio"
              name="theme"
              checked={appearance.globalTheme === "design1"}
              onChange={() => updateAppearance({ globalTheme: "design1" })}
            />
            <span><b>Design 1:</b> Mesh Gradient & Magnetic Filings (Deep blue & cyan glow)</span>
          </label>
          <label className="row">
            <input
              type="radio"
              name="theme"
              checked={appearance.globalTheme === "design2"}
              onChange={() => updateAppearance({ globalTheme: "design2" })}
            />
            <span><b>Design 2:</b> Aurora & Particle Flow (Particle drift with fluid wake)</span>
          </label>
          <label className="row">
            <input
              type="radio"
              name="theme"
              checked={appearance.globalTheme === "design3"}
              onChange={() => updateAppearance({ globalTheme: "design3" })}
            />
            <span><b>Design 3:</b> Prism & Spectral Light (Rainbow beam dispersion)</span>
          </label>
        </div>

        <div className="g2" style={{ marginTop: 8 }}>
          <div className="col" style={{ gap: 4 }}>
            <span className="sm mu">Darkness / Scrim: {Math.round(appearance.scrimOpacity * 100)}%</span>
            <input
              type="range"
              min="0.30"
              max="0.85"
              step="0.01"
              value={appearance.scrimOpacity}
              onChange={(e) => updateAppearance({ scrimOpacity: parseFloat(e.target.value) })}
            />
          </div>
          <div className="col" style={{ gap: 4 }}>
            <span className="sm mu">Animation Speed:</span>
            <select
              value={appearance.animationSpeed}
              onChange={(e) => updateAppearance({ animationSpeed: parseFloat(e.target.value) })}
            >
              <option value="0">Still / Paused (0x)</option>
              <option value="0.5">Calm (0.5x)</option>
              <option value="1">Normal (1.0x)</option>
              <option value="1.5">Fast (1.5x)</option>
            </select>
          </div>
        </div>

        {/* Detailed Color Controls */}
        <div className="col" style={{ marginTop: 12, borderTop: "1px solid #2a3036", paddingTop: 12, gap: 10 }}>
          <b className="sm">Fine-Tune Colors & Parameters:</b>

          {/* Design 1 controls */}
          <div className="col" style={{ gap: 6 }}>
            <span className="sm" style={{ color: "#4fd1b5" }}>Design 1 (Mesh Gradient) Colors:</span>
            <div className="rw wr" style={{ gap: 14 }}>
              <label className="rw sm" style={{ gap: 6 }}>
                Base 1:
                <input
                  type="color"
                  value={appearance.d1Color1}
                  onChange={(e) => updateAppearance({ d1Color1: e.target.value })}
                  style={{ width: 36, height: 32, padding: 2, cursor: "pointer" }}
                />
              </label>
              <label className="rw sm" style={{ gap: 6 }}>
                Base 2:
                <input
                  type="color"
                  value={appearance.d1Color2}
                  onChange={(e) => updateAppearance({ d1Color2: e.target.value })}
                  style={{ width: 36, height: 32, padding: 2, cursor: "pointer" }}
                />
              </label>
              <label className="rw sm" style={{ gap: 6 }}>
                Highlight:
                <input
                  type="color"
                  value={appearance.d1Color3}
                  onChange={(e) => updateAppearance({ d1Color3: e.target.value })}
                  style={{ width: 36, height: 32, padding: 2, cursor: "pointer" }}
                />
              </label>
            </div>
          </div>

          {/* Design 2 controls */}
          <div className="col" style={{ gap: 6, marginTop: 4 }}>
            <span className="sm" style={{ color: "#7fb4ff" }}>Design 2 (Particle Flow) Colors & Dust:</span>
            <div className="rw wr" style={{ gap: 14 }}>
              <label className="rw sm" style={{ gap: 6 }}>
                Color A:
                <input
                  type="color"
                  value={appearance.d2ColorA}
                  onChange={(e) => updateAppearance({ d2ColorA: e.target.value })}
                  style={{ width: 36, height: 32, padding: 2, cursor: "pointer" }}
                />
              </label>
              <label className="rw sm" style={{ gap: 6 }}>
                Color B:
                <input
                  type="color"
                  value={appearance.d2ColorB}
                  onChange={(e) => updateAppearance({ d2ColorB: e.target.value })}
                  style={{ width: 36, height: 32, padding: 2, cursor: "pointer" }}
                />
              </label>
              <label className="rw sm" style={{ gap: 6 }}>
                Particle Count:
                <input
                  type="range"
                  min="500"
                  max="3000"
                  step="250"
                  value={appearance.d2Count}
                  onChange={(e) => updateAppearance({ d2Count: parseInt(e.target.value) })}
                  style={{ width: 120 }}
                />
                <span>{appearance.d2Count}</span>
              </label>
            </div>
          </div>

          {/* Design 3 controls */}
          <div className="col" style={{ gap: 6, marginTop: 4 }}>
            <span className="sm" style={{ color: "#b79cff" }}>Design 3 (Prism) Dispersion:</span>
            <div className="rw wr" style={{ gap: 14 }}>
              <label className="rw sm" style={{ gap: 6 }}>
                Spread:
                <input
                  type="range"
                  min="0.2"
                  max="1.5"
                  step="0.05"
                  value={appearance.d3Spread}
                  onChange={(e) => updateAppearance({ d3Spread: parseFloat(e.target.value) })}
                  style={{ width: 120 }}
                />
                <span>{appearance.d3Spread}</span>
              </label>
              <label className="rw sm" style={{ gap: 6 }}>
                Intensity:
                <input
                  type="range"
                  min="0.3"
                  max="2.0"
                  step="0.05"
                  value={appearance.d3Intensity}
                  onChange={(e) => updateAppearance({ d3Intensity: parseFloat(e.target.value) })}
                  style={{ width: 120 }}
                />
                <span>{appearance.d3Intensity}</span>
              </label>
            </div>
          </div>

          <div style={{ marginTop: 8 }}>
            <button className="btn sm ghost" onClick={resetAppearance}>
              Reset Appearance to Defaults
            </button>
          </div>
        </div>
      </div>

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
