import os
import subprocess
import sys
import unittest

from scripts.run_t04_public import (
    CREATE_FLAGS,
    recorded_process_is_alive,
    terminate_recorded_process,
    windows_process_identity,
)


@unittest.skipUnless(os.name == "nt", "Launcher T04 mendukung Windows")
class T04LauncherTests(unittest.TestCase):
    def test_stop_rejects_pid_with_different_start_time_then_stops_owned_process(self):
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=CREATE_FLAGS,
        )
        self.addCleanup(lambda: process.terminate() if process.poll() is None else None)
        identity = None
        for _ in range(30):
            identity = windows_process_identity(process.pid)
            if identity:
                break
        self.assertIsNotNone(identity)
        self.assertTrue(recorded_process_is_alive(identity))

        stale_record = {**identity, "created": identity["created"] + 1}
        self.assertFalse(terminate_recorded_process(stale_record))
        self.assertIsNone(process.poll(), "PID daur ulang harus dibiarkan tetap berjalan")

        self.assertTrue(terminate_recorded_process(identity))
        process.wait(timeout=2)
        self.assertFalse(recorded_process_is_alive(identity))


if __name__ == "__main__":
    unittest.main()
