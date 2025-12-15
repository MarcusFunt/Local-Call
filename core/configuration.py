"""Profile and application configuration loading for the voice pipeline."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import yaml


@dataclass
class TransportConfig:
    """Transport-level configuration."""

    add_wav_header: bool = False
    session_timeout: Optional[int] = None


@dataclass
class STTConfig:
    """Speech-to-text settings."""

    server_url: str
    buffer_size_ms: int = 2000
    silence_timeout_ms: int = 500


@dataclass
class LLMConfig:
    """Language model settings."""

    host: str = "http://localhost:11434"
    persona_path: str = "config/persona_default.md"
    min_vram_gb: int = 12
    model_override: Optional[str] = None
    tool_call_limit: int = 3


@dataclass
class TTSConfig:
    """Text-to-speech settings."""

    server_url: str


@dataclass
class ProfileConfig:
    """Per-profile pipeline configuration."""

    name: str
    stt: STTConfig
    llm: LLMConfig
    tts: TTSConfig


@dataclass
class AppConfig:
    """Top-level configuration for the server and profiles."""

    default_profile: str
    transport: TransportConfig
    profiles: Dict[str, ProfileConfig]

    def profile(self, name: Optional[str]) -> ProfileConfig:
        target = name or self.default_profile
        if target not in self.profiles:
            raise KeyError(f"Unknown profile '{target}'. Known profiles: {', '.join(self.profiles)}")
        return self.profiles[target]


def _load_yaml(path: Path) -> Mapping[str, Any]:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, Mapping):
        raise ValueError(f"Config at {path} must be a mapping")
    return data


def _build_stt(config: Mapping[str, Any]) -> STTConfig:
    return STTConfig(**config)


def _build_llm(config: Mapping[str, Any]) -> LLMConfig:
    return LLMConfig(**config)


def _build_tts(config: Mapping[str, Any]) -> TTSConfig:
    return TTSConfig(**config)


def _build_transport(config: Mapping[str, Any]) -> TransportConfig:
    return TransportConfig(**config)


def _build_profile(name: str, config: Mapping[str, Any]) -> ProfileConfig:
    stt = _build_stt(config.get("stt", {}))
    llm = _build_llm(config.get("llm", {}))
    tts = _build_tts(config.get("tts", {}))
    return ProfileConfig(name=name, stt=stt, llm=llm, tts=tts)


def load_app_config(path: str | Path) -> AppConfig:
    """Load the application configuration from YAML."""

    config_map = _load_yaml(Path(path))
    default_profile = config_map.get("default_profile", "dev")
    transport = _build_transport(config_map.get("transport", {}))

    profiles: Dict[str, ProfileConfig] = {}
    for name, profile_cfg in config_map.get("profiles", {}).items():
        profiles[name] = _build_profile(name, profile_cfg or {})

    if not profiles:
        raise ValueError("No profiles defined in configuration file")

    return AppConfig(default_profile=default_profile, transport=transport, profiles=profiles)


_app_config: Optional[AppConfig] = None


def get_config() -> ProfileConfig:
    """Return the active profile configuration."""
    global _app_config
    if _app_config is None:
        _app_config = load_app_config("config/config.yml")

    profile_name = os.environ.get("PROFILE")
    return _app_config.profile(profile_name)
