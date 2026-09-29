"""运行配置。

所有可变路径与开关集中在此，便于本地开发(SQLite)与生产(PostgreSQL)共用同一套代码。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """服务配置。环境变量前缀 `EXAMDATA_`。"""

    model_config = SettingsConfigDict(
        env_prefix="EXAMDATA_",
        env_file=".env",
        extra="ignore",
    )

    # --- 数据根目录 ---
    data_dir: Path = Field(default=Path(".data"))

    # --- 数据库 ---
    # 本地开发默认 SQLite；生产用 PostgreSQL，例如：
    # postgresql+psycopg://examdata:examdata@localhost:5432/examdata
    database_url: str = "sqlite:///.data/examdata.db"

    # --- 抓取 ---
    user_agent: str = (
        "ExamDataBot/0.1 (+https://example.invalid/examdata; contact=ops@example.invalid)"
    )
    request_timeout_seconds: float = 30.0
    max_retries: int = 3
    retry_backoff_seconds: float = 2.0
    # 每个主机的最小请求间隔（秒），带抖动
    min_host_interval_seconds: float = 1.0
    host_interval_jitter_seconds: float = 0.5
    respect_robots: bool = True
    max_concurrency: int = 4

    # --- 解析器版本：派生数据重建的关键 ---
    parser_version: str = "0.1.0"

    @property
    def artifacts_dir(self) -> Path:
        return self.data_dir / "artifacts"

    @property
    def assets_dir(self) -> Path:
        return self.data_dir / "assets"

    @property
    def raw_pages_dir(self) -> Path:
        """保存原始 HTML 快照，用于页面结构回归与离线重放。"""
        return self.data_dir / "raw_pages"

    def ensure_dirs(self) -> None:
        for p in (self.data_dir, self.artifacts_dir, self.assets_dir, self.raw_pages_dir):
            p.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s
