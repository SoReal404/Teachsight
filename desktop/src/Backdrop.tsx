import { Component, ReactNode, useEffect, useState } from "react";
import {
  Shader,
  MeshGradient,
  CursorRipples,
  MagneticFilings,
  Aurora,
  ParticleFlow,
  Prism,
} from "shaders/react";
import {
  AppearanceSettings,
  loadAppearanceSettings,
  getProjectDesign,
} from "./theme";

class Guard extends Component<{ children: ReactNode }, { bad: boolean }> {
  state = { bad: false };
  static getDerivedStateFromError() { return { bad: true }; }
  componentDidCatch(error: any) {
    console.warn("Shader rendering fallback active:", error);
  }
  render() { return this.state.bad ? null : this.props.children; }
}

export default function Backdrop({ pid }: { pid?: string }) {
  const [settings, setSettings] = useState<AppearanceSettings>(loadAppearanceSettings);

  useEffect(() => {
    const onAppearanceChange = () => {
      setSettings(loadAppearanceSettings());
    };
    window.addEventListener("teachsight_appearance_changed", onAppearanceChange);
    return () => window.removeEventListener("teachsight_appearance_changed", onAppearanceChange);
  }, []);

  const gpu = typeof navigator !== "undefined" && "gpu" in navigator;
  const still = typeof window !== "undefined" && (
    !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ||
    settings.animationSpeed === 0
  );

  const activeDesign = settings.globalTheme !== "auto" ? settings.globalTheme : getProjectDesign(pid);

  // Gradient base colors corresponding to active design
  const baseGrad =
    activeDesign === "design2"
      ? "linear-gradient(135deg, #0b1a2e 0%, #00458f 50%, #15002a 100%)"
      : activeDesign === "design3"
      ? "linear-gradient(135deg, #181922 0%, #221235 50%, #0d2836 100%)"
      : "linear-gradient(135deg, #272833 0%, #00008f 60%, #00f2ff 100%)";

  return (
    <div className="bd" aria-hidden="true">
      <div className="bd-base" style={{ background: baseGrad }} />
      {gpu && (
        <Guard>
          <Shader toneMapping="aces" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
            {activeDesign === "design1" && (
              <>
                <MeshGradient
                  count={settings.d1Count}
                  drift={1}
                  seed={36}
                  smoothness={4.83}
                  speed={still ? 0 : settings.d1Speed * settings.animationSpeed}
                  stops={[
                    { color: settings.d1Color1, position: 0.2018 },
                    { color: settings.d1Color2, position: 1 },
                    { color: settings.d1Color3, position: 1 },
                  ]}
                  swirl={0.31}
                  variation={0.42}
                />
                <CursorRipples chromaticSplit={3} decay={6.2} intensity={20} radius={1} />
                <MagneticFilings />
              </>
            )}

            {activeDesign === "design2" && (
              <>
                <Aurora />
                <CursorRipples chromaticSplit={3} decay={6.2} intensity={20} radius={1} />
                <MagneticFilings />
                <ParticleFlow
                  ambient={still ? 0 : 0.03}
                  colorA={settings.d2ColorA}
                  colorB={settings.d2ColorB}
                  count={settings.d2Count}
                  force={settings.d2Force}
                  momentum={0}
                  size={0.3}
                />
              </>
            )}

            {activeDesign === "design3" && (
              <>
                <Prism
                  beamWidth={0.002}
                  boundingBox={{
                    x: { value: -1.0641, unit: "uv" },
                    y: { value: -0.7836, unit: "uv" },
                    width: { value: 2.2352, unit: "uv" },
                    height: { value: 2.3041, unit: "uv" },
                  }}
                  intensity={settings.d3Intensity}
                  saturation={settings.d3Saturation}
                  splitPosition={{
                    x: 0.42,
                    y: 0.37,
                  }}
                  spread={settings.d3Spread}
                />
                <CursorRipples chromaticSplit={2.9} decay={15.2} intensity={18.3} radius={0.7} />
              </>
            )}
          </Shader>
        </Guard>
      )}
      <div className="bd-scrim" style={{ background: `rgba(8, 10, 14, ${settings.scrimOpacity})` }} />
    </div>
  );
}
