"""Hostile child behaviors for future verify fixtures; not a Core runner."""
import os
import signal
import subprocess
import sys
import time

mode = sys.argv[1]
if mode == "exit":
    raise SystemExit(int(sys.argv[2]))
if mode == "signal":
    os.kill(os.getpid(), signal.SIGTERM)
elif mode == "pipe":
    subprocess.Popen([sys.executable, __file__, "hold"])
    print("pipe-holder-started", flush=True)
elif mode == "hold":
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    print("holding", flush=True)
    time.sleep(60)
elif mode == "timeout":
    print("waiting", flush=True)
    time.sleep(60)
else:
    raise SystemExit("unknown helper mode")
