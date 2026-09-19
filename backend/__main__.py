"""``python -m backend`` starts the HTTP API with uvicorn.

Environment: LINGJIAN_HOST (127.0.0.1), LINGJIAN_PORT (8000), LINGJIAN_WORKSPACE (./workspace),
LINGJIAN_CORS_ORIGINS (*).
"""
from __future__ import annotations

import os

import uvicorn

from backend.api import create_app


def main() -> None:
    host = os.environ.get("LINGJIAN_HOST", "127.0.0.1")
    port = int(os.environ.get("LINGJIAN_PORT", "8000"))
    print(f"灵剪后端已启动 · 接口文档 http://{host}:{port}/docs", flush=True)
    uvicorn.run(create_app(), host=host, port=port)


if __name__ == "__main__":
    main()
