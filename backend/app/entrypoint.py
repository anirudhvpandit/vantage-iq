import os
import subprocess
import sys
from pathlib import Path

import uvicorn


def main() -> None:
    if os.getenv("AUTO_MIGRATE", "true").casefold() == "true":
        config_path = Path(__file__).resolve().parents[1] / "alembic.ini"
        subprocess.run([sys.executable, "-m", "alembic", "-c", str(config_path), "upgrade", "head"], check=True)
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        proxy_headers=True,
        forwarded_allow_ips=os.getenv("FORWARDED_ALLOW_IPS", "127.0.0.1"),
        workers=int(os.getenv("WEB_CONCURRENCY", "1")),
    )


if __name__ == "__main__":
    main()
