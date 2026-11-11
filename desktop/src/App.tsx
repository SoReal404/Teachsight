import { useEffect, useState } from "react";
import { engine } from "./engine";
import Backdrop from "./Backdrop";
import Dashboard from "./Dashboard";
import Wizard from "./Wizard";
import Workspace from "./Workspace";
import Settings from "./Settings";
import { loadAppearanceSettings } from "./theme";

type View = { name: "dashboard" } | { name: "wizard" } | { name: "project"; pid: string } | { name: "settings" };

export default function App() {
  const [view, setView] = useState<View>({ name: "dashboard" });
  const [projects, setProjects] = useState<any[]>([]);
  const [offline, setOffline] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(() => localStorage.getItem("teachsight_sidebar_open") !== "false");
  const [appearance, setAppearance] = useState(loadAppearanceSettings);

  const toggleSidebar = () => {
    setSidebarOpen((prev) => {
      const next = !prev;
      localStorage.setItem("teachsight_sidebar_open", String(next));
      return next;
    });
  };

  const refresh = async () => {
    try {
      setProjects(await engine.projects());
      setOffline(false);
    } catch {
      setOffline(true);
    }
  };

  useEffect(() => {
    refresh();
  }, [view.name]);

  useEffect(() => {
    const onAppearanceChange = () => setAppearance(loadAppearanceSettings());
    window.addEventListener("teachsight_appearance_changed", onAppearanceChange);
    return () => window.removeEventListener("teachsight_appearance_changed", onAppearanceChange);
  }, []);

  async function create(name: string, brief: any) {
    try {
      const p = await engine.createProject(name, brief);
      await refresh();
      setView({ name: "project", pid: p.id });
    } catch {
      setOffline(true);
      setView({ name: "dashboard" });
    }
  }

  async function remove(p: any) {
    if (!window.confirm(`Delete "${p.name}" and everything in it (answers and trained models)? Your original pictures are not touched.`)) return;
    await engine.deleteProject(p.id);
    refresh();
  }

  const isProject = view.name === "project";
  const activePid = isProject ? view.pid : "";
  const shaded = view.name === "dashboard" || view.name === "wizard" || (isProject && appearance.trainingBackground);

  return (
    <div className="app">
      <aside className={"side" + (sidebarOpen ? "" : " collapsed")}>
        <div className="side-head">
          <span style={{ fontWeight: 700, letterSpacing: "-0.01em", fontSize: 18, color: "#4fd1b5" }}>Teachsight</span>
          <button className="side-toggle-btn" onClick={toggleSidebar} title="Collapse sidebar to free screen space">
            ◀
          </button>
        </div>
        <button className="newb" onClick={() => setView({ name: "wizard" })}>+ New project</button>
        <div className={"it" + (view.name === "dashboard" ? " on" : "")} onClick={() => setView({ name: "dashboard" })}>All projects</div>
        <div className="lbl">Recent</div>
        <div className="list">
          {projects.slice(0, 8).map((p) => (
            <div key={p.id} className={"it" + (p.id === activePid ? " on" : "")} onClick={() => setView({ name: "project", pid: p.id })}>
              {p.name}
            </div>
          ))}
        </div>
        <div className={"it" + (view.name === "settings" ? " on" : "")} onClick={() => setView({ name: "settings" })}>Settings</div>
      </aside>

      <main className="main">
        {shaded && <Backdrop pid={activePid} />}
        <div className={"stage" + (shaded ? " shaded" : "")}>
          {view.name === "dashboard" && (
            <Dashboard
              projects={projects}
              offline={offline}
              onRetry={refresh}
              onNew={() => setView({ name: "wizard" })}
              onOpen={(id) => setView({ name: "project", pid: id })}
              onDelete={remove}
            />
          )}
          {view.name === "wizard" && <Wizard onCancel={() => setView({ name: "dashboard" })} onCreate={create} />}
          {view.name === "project" && (
            <Workspace
              key={view.pid}
              pid={view.pid}
              sidebarOpen={sidebarOpen}
              onToggleSidebar={toggleSidebar}
              onBack={() => setView({ name: "dashboard" })}
              onChanged={refresh}
              onSettings={() => setView({ name: "settings" })}
            />
          )}
          {view.name === "settings" && <Settings />}
        </div>
      </main>
    </div>
  );
}
