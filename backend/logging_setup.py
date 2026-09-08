"""集中的日誌設定。

原本的問題：
- 設定散在 `monitor/utils.setup_logging()`，而且是在**模組 import 時**呼叫。
  於是只要 import 任何 monitor 模組就會掛上檔案 handler——`tr_rooms` 開始
  共用 `monitor.semester` 之後，FastAPI 後端也會掛上 worker 的 `ntust_monitor.log`，
  兩個 process 寫同一個輪替檔，午夜輪替會互相搶檔。
- `email_sender` 用 `getLogger(__name__)`，那棵樹沒有 handler、root 也沒有，
  寄信失敗的日誌等於丟掉。

現在的規則：
- **模組只取 logger**（`get_logger(__name__)`），不設定 handler，也沒有 import 時副作用。
- **只有進入點設定 handler**（worker 用 `configure_worker_logging()`；
  FastAPI 後端交給 uvicorn，不自己開檔）。
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

#: monitor 相關模組共用的 logger 名稱；`logs/ntust_monitor.log` 就是這棵樹寫的。
MONITOR_LOGGER_NAME = "ntust_monitor"

LOG_FORMAT = "%(asctime)s - [%(name)s] - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str | None = None) -> logging.Logger:
    """取得 logger。傳模組名時掛在 monitor logger 底下，讓設定只需做一次。

    只取不設定：handler 由進入點決定，模組 import 不應該產生檔案。
    """
    if not name or name == MONITOR_LOGGER_NAME:
        return logging.getLogger(MONITOR_LOGGER_NAME)
    suffix = name.rsplit(".", 1)[-1]
    return logging.getLogger(f"{MONITOR_LOGGER_NAME}.{suffix}")


def configure_worker_logging(
    level: int = logging.INFO,
    log_to_file: bool = True,
    log_to_console: bool = False,
) -> logging.Logger:
    """worker 進入點呼叫一次：單一檔案 + 每日輪替，保留 7 天。

    重複呼叫是安全的（已有 handler 就不再加）。
    """
    logger = logging.getLogger(MONITOR_LOGGER_NAME)
    logger.setLevel(level)
    if logger.handlers:
        return logger

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    if log_to_file:
        # 以 repo 根目錄為準（backend/logging_setup.py -> parents[1]），
        # 不受啟動時的 cwd 影響（uvicorn 從 backend/ 啟動）。
        log_dir = Path(__file__).resolve().parents[1] / "logs"
        log_dir.mkdir(exist_ok=True)
        handler = TimedRotatingFileHandler(
            log_dir / "ntust_monitor.log",
            when="midnight",
            backupCount=7,
            encoding="utf-8",
            utc=False,
        )
        handler.setLevel(level)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    if log_to_console:
        # stdout，讓工作排程器導向的 logs\monitor.log 收得到
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(level)
        console.setFormatter(formatter)
        logger.addHandler(console)

    return logger
