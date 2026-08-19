"""環境變數設定（spec §3 密鑰邊界、§5 LLM、§3.6 防濫用）。

硬性原則：OPENROUTER_API_KEY 只存在後端，永不下發前端、永不寫入 log。
本模組的 __repr__ / 任何序列化都不會帶出金鑰。
"""

from __future__ import annotations

import logging
import os
import secrets
from pathlib import Path

log = logging.getLogger("ctf.config")


def _env_str(name: str, default: str = "") -> str:
    v = os.environ.get(name)
    return default if v is None or v.strip() == "" else v.strip()


def _env_int(name: str, default: int) -> int:
    raw = _env_str(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        log.warning("環境變數 %s=%r 不是整數，改用預設值 %s", name, raw, default)
        return default


def _env_float(name: str, default: float) -> float:
    raw = _env_str(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        log.warning("環境變數 %s=%r 不是數字，改用預設值 %s", name, raw, default)
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = _env_str(name).lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


class Settings:
    """啟動時讀一次；後續唯讀。"""

    def __init__(self) -> None:
        # ---- 路徑 ----
        self.data_dir = Path(_env_str("DATA_DIR", "./data"))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(_env_str("DB_PATH", str(self.data_dir / "ctf.db")))
        self.challenges_path = Path(_env_str("CHALLENGES_PATH", "./challenges.json"))
        self.static_dir = Path(_env_str("STATIC_DIR", str(Path(__file__).resolve().parent.parent / "static")))

        # ---- 密鑰（spec §3.1 / §6）----
        # 前端永遠拿不到；/api/* 任何回應都不含這兩個值。
        self.openrouter_api_key = _env_str("OPENROUTER_API_KEY")
        self.server_secret = self._resolve_server_secret()
        self.admin_token = _env_str("ADMIN_TOKEN")

        # ---- OpenRouter（spec §5）----
        self.openrouter_url = _env_str(
            "OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions"
        )
        self.model = _env_str("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct")
        self.http_referer = _env_str("HTTP_REFERER", "https://ctf.lab.example")
        self.x_title = _env_str("X_TITLE", "NCSE AI Security CTF")
        self.llm_timeout = _env_float("LLM_TIMEOUT_SECONDS", 20.0)
        self.llm_max_retries = _env_int("LLM_MAX_RETRIES", 2)
        self.llm_max_concurrency = _env_int("LLM_MAX_CONCURRENCY", 32)
        # 離線 / UI 開發用：不打 OpenRouter，回傳可預期的假回覆。
        self.fake_llm = _env_bool("FAKE_LLM", False)

        # ---- 防濫用（spec §3.6）----
        # 以下每一個都用 **0 = 不限**。活動當天為了不卡住學員全部設 0，
        # 此時 GLOBAL_TOKEN_BUDGET 是唯一的成本閘門，務必保持啟用。
        self.rate_per_challenge_per_min = _env_int("RATE_PER_CHALLENGE_PER_MIN", 0)
        self.rate_per_user_per_min = _env_int("RATE_PER_USER_PER_MIN", 0)
        self.rate_login_per_min = _env_int("RATE_LOGIN_PER_MIN", 0)
        # spec §3.6 要求「嘗試上限」，§12 又要求「允許無限次嘗試」——這裡採後者。
        self.max_attempts_per_challenge = _env_int("MAX_ATTEMPTS_PER_CHALLENGE", 0)
        self.def_max_submissions = _env_int("DEF_MAX_SUBMISSIONS", 0)
        # DEF 一次提交 = 15 次模型呼叫，是全平臺最貴的操作。
        self.def_rate_per_min = _env_int("DEF_RATE_PER_MIN", 0)
        self.def_require_usability = _env_bool("DEF_REQUIRE_USABILITY", True)

        # 全域 token 預算（prompt + completion 累計）。0 = 無上限。
        self.global_token_budget = _env_int("GLOBAL_TOKEN_BUDGET", 0)
        self.budget_warn_ratio = _env_float("BUDGET_WARN_RATIO", 0.8)

        # ---- 輸入長度上限（spec §3.6 / §5）----
        self.max_user_message_chars = _env_int("MAX_USER_MESSAGE_CHARS", 2000)
        self.max_history_messages = _env_int("MAX_HISTORY_MESSAGES", 6)
        self.max_document_chars = _env_int("MAX_DOCUMENT_CHARS", 4000)
        self.max_defense_prompt_chars = _env_int("MAX_DEFENSE_PROMPT_CHARS", 4000)
        self.max_display_name_chars = _env_int("MAX_DISPLAY_NAME_CHARS", 20)

        # ---- session / nonce ----
        self.session_ttl_seconds = _env_int("SESSION_TTL_SECONDS", 60 * 60 * 24)
        self.xss_nonce_ttl_seconds = _env_int("XSS_NONCE_TTL_SECONDS", 900)

        # ---- 活動流程 ----
        self.seed_users = _env_int("SEED_USERS", 0)
        self.final_open_default = _env_bool("FINAL_OPEN_DEFAULT", False)

        self.app_env = _env_str("APP_ENV", "prod")

    def _resolve_server_secret(self) -> str:
        """SERVER_SECRET 必須跨重啟穩定，否則所有 per-user flag 會變。

        優先序：環境變數 > data_dir/server_secret 檔案 > 產生新的並寫入檔案。
        """
        env_secret = _env_str("SERVER_SECRET")
        if env_secret:
            return env_secret

        secret_file = self.data_dir / "server_secret"
        if secret_file.exists():
            val = secret_file.read_text(encoding="utf-8").strip()
            if val:
                log.warning("SERVER_SECRET 未設定，沿用 %s 內既有的秘密。", secret_file)
                return val

        val = secrets.token_hex(32)
        secret_file.write_text(val, encoding="utf-8")
        try:
            secret_file.chmod(0o600)
        except OSError:  # pragma: no cover - 某些檔案系統不支援
            pass
        log.warning(
            "SERVER_SECRET 未設定，已自動產生並寫入 %s。"
            "正式活動請改用環境變數，並確保此檔案（或 volume）不會被刪除，"
            "否則所有學員的 flag 都會改變。",
            secret_file,
        )
        return val

    # 防止金鑰在 log / traceback / repr 中外洩（spec §3.1）
    def __repr__(self) -> str:  # pragma: no cover
        return f"<Settings app_env={self.app_env} model={self.model} data_dir={self.data_dir}>"

    __str__ = __repr__


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings_for_tests() -> None:
    """測試用：讓下次 get_settings() 重新讀環境變數。"""
    global _settings
    _settings = None
