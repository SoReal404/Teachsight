export interface AppearanceSettings {
  globalTheme: "auto" | "design1" | "design2" | "design3";
  trainingBackground: boolean;
  scrimOpacity: number; // 0.3 to 0.85
  animationSpeed: number; // 0 (still) to 2.0
  // Design 1: Mesh Gradient + Magnetic Filings
  d1Color1: string;
  d1Color2: string;
  d1Color3: string;
  d1Count: number;
  d1Speed: number;
  // Design 2: Aurora + Particle Flow
  d2ColorA: string;
  d2ColorB: string;
  d2Count: number;
  d2Force: number;
  // Design 3: Prism + Ripples
  d3Intensity: number;
  d3Saturation: number;
  d3Spread: number;
}

export const DEFAULT_APPEARANCE: AppearanceSettings = {
  globalTheme: "auto",
  trainingBackground: true,
  scrimOpacity: 0.62,
  animationSpeed: 1.0,
  d1Color1: "#272833",
  d1Color2: "#00008f",
  d1Color3: "#00f2ff",
  d1Count: 6,
  d1Speed: 10,
  d2ColorA: "#007dfa",
  d2ColorB: "#ff0808",
  d2Count: 1000,
  d2Force: 0.4,
  d3Intensity: 0.95,
  d3Saturation: 1.0,
  d3Spread: 0.77,
};

const STORAGE_KEY = "teachsight_appearance_settings";
const THEME_PREFIX = "teachsight_project_theme_";

export function loadAppearanceSettings(): AppearanceSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      return { ...DEFAULT_APPEARANCE, ...JSON.parse(raw) };
    }
  } catch {
    // fallback to defaults
  }
  return { ...DEFAULT_APPEARANCE };
}

export function saveAppearanceSettings(settings: Partial<AppearanceSettings>): AppearanceSettings {
  const current = loadAppearanceSettings();
  const updated = { ...current, ...settings };
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    window.dispatchEvent(new CustomEvent("teachsight_appearance_changed", { detail: updated }));
  } catch {
    // ignore
  }
  return updated;
}

/**
 * Gets or assigns a persistent random design for a project.
 * Ensures the SAME project always gets the SAME design even after app restart.
 */
export function getProjectDesign(pid?: string): "design1" | "design2" | "design3" {
  if (!pid) return "design1";
  
  const key = THEME_PREFIX + pid;
  try {
    const existing = localStorage.getItem(key);
    if (existing === "design1" || existing === "design2" || existing === "design3") {
      return existing;
    }
    
    // Deterministic hash based on pid string so it's pseudo-random but strictly reproducible
    let hash = 0;
    for (let i = 0; i < pid.length; i++) {
      hash = (hash << 5) - hash + pid.charCodeAt(i);
      hash |= 0;
    }
    const designs: ("design1" | "design2" | "design3")[] = ["design1", "design2", "design3"];
    const chosen = designs[Math.abs(hash) % designs.length];
    localStorage.setItem(key, chosen);
    return chosen;
  } catch {
    return "design1";
  }
}

export function setProjectDesign(pid: string, design: "design1" | "design2" | "design3") {
  if (!pid) return;
  try {
    localStorage.setItem(THEME_PREFIX + pid, design);
    window.dispatchEvent(new CustomEvent("teachsight_appearance_changed"));
  } catch {
    // ignore
  }
}
