# One-time runtime install. Never touches system Python. Safe to re-run: exits fast if already installed.
param(
  [string]$Root = "$env:LOCALAPPDATA\NoCodeCV\runtime",
  [string]$BaseReq = "$PSScriptRoot\..\engine\requirements-base.txt"
)
$ErrorActionPreference = "Stop"
$RuntimeVersion = 1
function Emit($step, $pct, $msg) { Write-Output (@{ step = $step; percent = $pct; message = $msg } | ConvertTo-Json -Compress) }
function Run($exe, $argList) { & $exe @argList; if ($LASTEXITCODE -ne 0) { throw "$exe failed ($LASTEXITCODE)" } }

New-Item -ItemType Directory -Force $Root | Out-Null
$marker = Join-Path $Root "runtime.json"
if (Test-Path $marker) {
  $m = Get-Content $marker | ConvertFrom-Json
  if ($m.version -eq $RuntimeVersion) { Emit "runtime" 100 "Already installed"; exit 0 }
}
$env:UV_CACHE_DIR = Join-Path $Root "cache"
$env:UV_PYTHON_INSTALL_DIR = Join-Path $Root "python"
$uv = Join-Path $Root "bin\uv.exe"

if (-not (Test-Path $uv)) {
  Emit "helper" 5 "Downloading setup helper"
  $zip = Join-Path $env:TEMP "uv.zip"
  Invoke-WebRequest "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip" -OutFile $zip
  New-Item -ItemType Directory -Force (Split-Path $uv) | Out-Null
  Expand-Archive $zip -DestinationPath (Split-Path $uv) -Force
}
Emit "python" 15 "Installing a private copy of Python"
Run $uv @("python", "install", "3.11")
$envDir = Join-Path $Root "env"
Run $uv @("venv", $envDir, "--python", "3.11")
$py = Join-Path $envDir "Scripts\python.exe"

# Pick the right PyTorch build for this PC. CUDA wheels bundle the CUDA runtime, so only the NVIDIA driver is needed.
$index = "https://download.pytorch.org/whl/cpu"; $kind = "cpu"
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
  $drv = [version]((& nvidia-smi --query-gpu=driver_version --format=csv,noheader | Select-Object -First 1).Trim())
  if ($drv -ge [version]"551.61") { $index = "https://download.pytorch.org/whl/cu124"; $kind = "cu124" }
  elseif ($drv -ge [version]"522.06") { $index = "https://download.pytorch.org/whl/cu118"; $kind = "cu118" }
}
Emit "torch" 30 "Installing the AI engine ($kind). This is the big download, done only once."
Run $uv @("pip", "install", "--python", $py, "torch", "torchvision", "--index-url", $index)
Emit "libs" 85 "Installing the remaining libraries"
Run $uv @("pip", "install", "--python", $py, "-r", $BaseReq)

@{ version = $RuntimeVersion; torch = $kind; installed = (Get-Date).ToString("s") } | ConvertTo-Json | Set-Content $marker
Emit "runtime" 100 "Ready"
