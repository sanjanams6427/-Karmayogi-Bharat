"""
Verify the global per-GPU model lock serializes concurrent dub jobs so two
languages never load models on the same GPU at once (the freeze cause).

Run:  venv\\Scripts\\python.exe scripts\\test_gpu_lock.py
"""
import sys, threading, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.dubbing_pipeline import _get_gpu_model_lock

failures = []


def check(name, cond, extra=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {extra}")
    if not cond:
        failures.append(name)


# 1. Same GPU key returns the SAME lock object (so jobs actually serialize).
l1 = _get_gpu_model_lock()
l2 = _get_gpu_model_lock()
check("same GPU returns same lock object", l1 is l2)

# 2. Simulate two "jobs" that each hold the lock while 'loading models'.
#    With serialization, their critical sections must NOT overlap.
overlap = {"count": 0, "active": 0, "max_active": 0}
lock_for_run = _get_gpu_model_lock()


def job(name):
    lock_for_run.acquire()
    try:
        overlap["active"] += 1
        overlap["max_active"] = max(overlap["max_active"], overlap["active"])
        time.sleep(0.2)  # simulate model load + inference
        overlap["active"] -= 1
    finally:
        lock_for_run.release()


t1 = threading.Thread(target=job, args=("hin",))
t2 = threading.Thread(target=job, args=("pan",))
t1.start(); t2.start()
t1.join(); t2.join()

check("two jobs never ran models concurrently (max_active==1)",
      overlap["max_active"] == 1, f"max_active={overlap['max_active']}")

# 3. Lock is fully released after use (re-acquirable).
got = lock_for_run.acquire(blocking=False)
check("lock released and re-acquirable after jobs", got)
if got:
    lock_for_run.release()

print()
if failures:
    print(f"{len(failures)} FAILED: {failures}")
    sys.exit(1)
print("ALL PASSED — concurrent GPU model loading is serialized")
sys.exit(0)
