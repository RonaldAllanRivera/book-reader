import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv


@dataclass
class SLZConfig:
    base_url: str


@dataclass
class AutomationConfig:
    book_title: str
    read_scroll_step_seconds: float
    read_total_seconds: int
    max_quiz_questions: int
    headless: bool


@dataclass
class LLMConfig:
    provider: str
    base_url: str
    model: str
    api_key: str


@dataclass
class AppConfig:
    slz: SLZConfig
    automation: AutomationConfig
    llm: LLMConfig
    username: str
    password: str


def _load_raw_config() -> Dict[str, Any]:
    base_dir = Path(__file__).resolve().parents[2]
    config_path = base_dir / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"config.yaml not found at {config_path}")
    with config_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def load_config() -> AppConfig:
    load_dotenv()

    raw = _load_raw_config()
    slz_cfg = raw.get("slz", {})
    auto_cfg = raw.get("automation", {})
    llm_cfg = raw.get("llm", {})

    username = os.getenv("SLZ_USERNAME", "")
    password = os.getenv("SLZ_PASSWORD", "")
    api_key = os.getenv("OPENAI_API_KEY", "")

    # Username and password are optional because the user may prefer to log in manually.
    # However, an API key is still required for the remote LLM provider.
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY must be set in environment or .env")

    slz_base_url = os.getenv(
        "SLZ_BASE_URL",
        slz_cfg.get("base_url", "https://scholasticlearningzone.com"),
    )

    slz = SLZConfig(
        base_url=slz_base_url,
    )

    automation = AutomationConfig(
        book_title=auto_cfg.get("book_title", ""),
        read_scroll_step_seconds=float(auto_cfg.get("read_scroll_step_seconds", 2.0)),
        read_total_seconds=int(auto_cfg.get("read_total_seconds", 120)),
        max_quiz_questions=int(auto_cfg.get("max_quiz_questions", 20)),
        headless=bool(auto_cfg.get("headless", False)),
    )

    llm = LLMConfig(
        provider=llm_cfg.get("provider", "openai"),
        base_url=llm_cfg.get("base_url", "https://api.openai.com/v1").rstrip("/"),
        model=llm_cfg.get("model", "gpt-4o-mini"),
        api_key=api_key,
    )

    return AppConfig(
        slz=slz,
        automation=automation,
        llm=llm,
        username=username,
        password=password,
    )
