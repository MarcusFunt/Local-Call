"""Model selection utilities for Ollama-backed chat models."""
from __future__ import annotations

import importlib
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DEFAULT_QWEN = "qwen3:14b"
DEFAULT_GEMMA = "gemma2:2b"
DEFAULT_PERSONA_PATH = Path("config/persona_default.md")


@dataclass
class ModelRouter:
    """Choose an Ollama model based on runtime profile and GPU memory."""

    persona_path: Path = DEFAULT_PERSONA_PATH
    min_vram_gb: int = 12
    override_model: Optional[str] = None

    def select_model(self, profile: str) -> str:
        if self.override_model:
            return self.override_model

        if profile == "prod":
            return self._prod_model()

        return self._dev_model()

    def load_persona(self) -> str:
        return self.persona_path.read_text(encoding="utf-8").strip()

    def _prod_model(self) -> str:
        vram_gb = _detect_gpu_vram_gb()
        if vram_gb is not None and vram_gb >= self.min_vram_gb:
            return DEFAULT_QWEN
        return DEFAULT_GEMMA

    def _dev_model(self) -> str:
        vram_gb = _detect_gpu_vram_gb()
        if vram_gb is not None and vram_gb >= self.min_vram_gb:
            return DEFAULT_QWEN
        return DEFAULT_GEMMA


def _detect_gpu_vram_gb() -> Optional[int]:
    """Return the total VRAM of the first GPU in GiB, if available."""

    if importlib.util.find_spec("torch"):
        import torch

        if torch.cuda.is_available():
            total_bytes = torch.cuda.get_device_properties(0).total_memory
            return int(total_bytes // (1024**3))

    nvidia_smi = os.environ.get("NVIDIA_SMI", "nvidia-smi")
    try:
        output = subprocess.check_output(
            [nvidia_smi, "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        ).strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return None

    if not output:
        return None

    first_line = output.splitlines()[0].strip()
    if first_line.isdigit():
        return int(first_line) // 1024 if int(first_line) > 0 else None
    return None
