import { Component, ReactNode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";

class Boundary extends Component<{ children: ReactNode }, { err: string }> {
  state = { err: "" };
  static getDerivedStateFromError(e: Error) { return { err: String(e?.stack || e) }; }
  render() {
    return this.state.err
      ? <pre style={{ color: "#ff8a80", background: "#15171a", padding: 24, margin: 0, minHeight: "100vh", whiteSpace: "pre-wrap" }}>{"The app crashed. Please send this text to the developer:\n\n" + this.state.err}</pre>
      : this.props.children;
  }
}
window.addEventListener("error", (e) => { document.body.insertAdjacentHTML("afterbegin", `<pre style="color:#ff8a80;background:#15171a;margin:0;padding:12px">${String(e.message)}</pre>`); });
createRoot(document.getElementById("root")!).render(<Boundary><App /></Boundary>);
