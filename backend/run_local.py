import asyncio
import sys
from pathlib import Path

import uvicorn


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    config = uvicorn.Config("app.main:app", host="127.0.0.1", port=8000)
    server = uvicorn.Server(config)
    if sys.platform == "win32":
        with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
            runner.run(server.serve())
    else:
        server.run()
