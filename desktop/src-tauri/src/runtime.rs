// Tauri commands: first-run runtime install and engine start. Untested first draft.
// Register in main.rs:  .invoke_handler(tauri::generate_handler![runtime::ensure_runtime, runtime::start_engine])
use std::{io::{BufRead, BufReader}, path::PathBuf, process::{Command, Stdio}};
use tauri::{path::BaseDirectory, AppHandle, Emitter, Manager};

#[cfg(windows)]
use std::os::windows::process::CommandExt;

fn runtime_root() -> PathBuf {
    let base = std::env::var("LOCALAPPDATA").map(PathBuf::from).unwrap_or_else(|_| std::env::temp_dir());
    base.join("NoCodeCV").join("runtime")
}

#[tauri::command]
pub async fn ensure_runtime(app: AppHandle) -> Result<(), String> {
    let script = app.path().resolve("runtime/setup_runtime.ps1", BaseDirectory::Resource).map_err(|e| e.to_string())?;
    let req = app.path().resolve("engine/requirements-base.txt", BaseDirectory::Resource).map_err(|e| e.to_string())?;
    let mut cmd = Command::new("powershell");
    cmd.args(["-NoProfile", "-ExecutionPolicy", "Bypass", "-File"]).arg(script)
        .arg("-Root").arg(runtime_root()).arg("-BaseReq").arg(req).stdout(Stdio::piped());
    #[cfg(windows)]
    cmd.creation_flags(0x08000000); // no console window
    let mut child = cmd.spawn().map_err(|e| e.to_string())?;
    if let Some(out) = child.stdout.take() {
        for line in BufReader::new(out).lines().flatten() {
            let _ = app.emit("runtime-progress", line); // JSON: {step, percent, message}
        }
    }
    let status = child.wait().map_err(|e| e.to_string())?;
    if status.success() { Ok(()) } else { Err("Runtime setup failed".into()) }
}

#[tauri::command]
pub fn start_engine(app: AppHandle) -> Result<u32, String> {
    let py = runtime_root().join("env").join("Scripts").join("python.exe");
    let engine_dir = app.path().resolve("engine", BaseDirectory::Resource).map_err(|e| e.to_string())?;
    let mut cmd = Command::new(py);
    cmd.args(["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8765"]).current_dir(engine_dir);
    #[cfg(windows)]
    cmd.creation_flags(0x08000000);
    let child = cmd.spawn().map_err(|e| e.to_string())?;
    Ok(child.id()) // TODO: kill on app exit, pick a free port
}
