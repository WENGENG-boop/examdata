"""W4b evidence rig: run the candidate read API on a loopback ephemeral port.

Usage: python -B start_api.py <snapshot-root> [operations-root|none]
Prints 'W4B_API_PORT=<port>' once the socket is chosen, before serving.
"""
from __future__ import annotations

import os
import socket
import sys
from pathlib import Path


def main() -> None:
    sys.dont_write_bytecode = True
    snapshot = Path(sys.argv[1]).resolve()
    ops = sys.argv[2] if len(sys.argv) > 2 else "none"
    os.environ["EXAMDATA_INTEGRATION_ROOT"] = str(snapshot)
    if ops != "none":
        os.environ["EXAMDATA_OPERATIONS_ROOT"] = str(Path(ops).resolve())
    else:
        os.environ.pop("EXAMDATA_OPERATIONS_ROOT", None)
    sys.path.insert(0, str(snapshot / "src"))

    import uvicorn  # noqa: E402
    from examdata.integration.api.app import create_app  # noqa: E402
    from examdata.integration.api.dataset import default_dataset  # noqa: E402

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    print(f"W4B_API_PORT={port}", flush=True)
    uvicorn.run(create_app(dataset=default_dataset()), host="127.0.0.1", port=port,
                log_level="info")


if __name__ == "__main__":
    main()
