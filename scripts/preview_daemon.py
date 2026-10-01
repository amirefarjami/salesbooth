#!/usr/bin/env python3
"""Start the preview admin server fully detached (double-fork daemon).

macOS lacks setsid; a plain nohup child can be reaped when the terminal
runner tears down its process group. Double-fork + os.setsid orphans the
server so launchd inherits it and it outlives this conversation.

Prints the daemon PID to stdout.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / ".freebuff" / "preview.log"


def main() -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    r, w = os.pipe()
    pid = os.fork()
    if pid == 0:
        # child: detach, fork again so the grandchild is orphaned (init-owned)
        os.close(r)
        os.setsid()
        inner = os.fork()
        if inner > 0:
            os._exit(0)  # middle parent exits immediately
        # grandchild: report pid, then exec the server
        os.write(w, f"{os.getpid()}\n".encode())
        os.close(w)
        os.chdir(str(ROOT))
        log_fd = os.open(str(LOG), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        os.dup2(log_fd, 1)
        os.dup2(log_fd, 2)
        devnull = os.open(os.devnull, os.O_RDONLY)
        os.dup2(devnull, 0)
        python = str(ROOT / ".venv" / "bin" / "python")
        os.execv(python, [python, "-m", "uvicorn", "admin.app:app",
                          "--host", "127.0.0.1", "--port", "8000"])
        os._exit(127)
    # parent: wait for grandchild pid and print it
    os.close(w)
    data = os.read(r, 32)
    os.close(r)
    os.waitpid(pid, 0)  # reap the middle parent
    print(data.decode().strip() or "fork-failed")


if __name__ == "__main__":
    main()
