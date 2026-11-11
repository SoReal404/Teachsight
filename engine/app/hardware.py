"""Hardware probe: detects CPU, RAM, disk, and verifies real GPU / CUDA tensor capability."""
from __future__ import annotations
import os, shutil, subprocess
import psutil


def _gpu() -> dict | None:
    # 1. Try PyTorch CUDA with real allocation test
    try:
        import torch
        if torch.cuda.is_available():
            dev_idx = 0
            p = torch.cuda.get_device_properties(dev_idx)
            total_bytes = p.total_memory
            total_gb = round(total_bytes / (1024**3), 2)
            
            # Check free VRAM
            try:
                free_bytes, _ = torch.cuda.mem_get_info(dev_idx)
                free_gb = round(free_bytes / (1024**3), 2)
            except Exception:
                free_gb = total_gb

            # Verify actual tensor allocation
            cuda_verified = False
            try:
                t = torch.zeros((1,), device="cuda")
                cuda_verified = bool(t.is_cuda)
                del t
                torch.cuda.empty_cache()
            except Exception:
                cuda_verified = False

            return {
                "name": p.name,
                "vram_gb": total_gb,
                "vram_free_gb": free_gb,
                "cuda_verified": cuda_verified,
                "cuda_version": torch.version.cuda or "Built-in",
                "torch_cuda": True,
            }
    except Exception:
        pass

    # 2. Fallback to nvidia-smi if torch doesn't have CUDA
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free,driver_version", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        ).stdout.strip().splitlines()
        if out:
            parts = [x.strip() for x in out[0].split(",")]
            name = parts[0]
            total_mb = int(parts[1]) if len(parts) > 1 else 0
            free_mb = int(parts[2]) if len(parts) > 2 else 0
            driver = parts[3] if len(parts) > 3 else "Unknown"
            return {
                "name": name,
                "vram_gb": round(total_mb / 1024, 2),
                "vram_free_gb": round(free_mb / 1024, 2),
                "driver_version": driver,
                "cuda_verified": False,
                "torch_cuda": False,
                "note": "GPU detected via system driver, but current Python environment is using CPU PyTorch."
            }
    except Exception:
        pass
    return None


def probe(path: str = ".") -> dict:
    gpu = _gpu()
    vm = psutil.virtual_memory()
    
    info = {
        "cpu_cores": os.cpu_count() or 4,
        "ram_gb": round(vm.total / (1024**3), 1),
        "ram_free_gb": round(vm.available / (1024**3), 1),
        "ram_percent": vm.percent,
        "disk_free_gb": round(shutil.disk_usage(path).free / (1024**3), 1),
        "gpu": gpu,
    }

    # Decide device
    if gpu and gpu.get("torch_cuda", True) and gpu.get("cuda_verified", True):
        info["device"] = "cuda"
        v_free = gpu.get("vram_free_gb", gpu.get("vram_gb", 4))
        # Batch size recommendation based on available VRAM
        if v_free >= 8:
            b_size, im_size = 32, 224
        elif v_free >= 5:
            b_size, im_size = 16, 224
        elif v_free >= 3:
            b_size, im_size = 8, 224
        else:
            b_size, im_size = 4, 192
    else:
        info["device"] = "cpu"
        b_size, im_size = 8, 160

    info["recommended"] = {
        "batch_size": b_size,
        "image_size": im_size,
        "device": info["device"],
    }
    return info
