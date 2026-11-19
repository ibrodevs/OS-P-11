"""End-to-end Linux tests of C fault counters and actual local/cold access."""
import csv
import io
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
C_EXE = ROOT / "c" / "page_faults"


@unittest.skipUnless(sys.platform.startswith("linux") and shutil.which("make") and shutil.which("cc"),
                     "Linux with make and a C compiler is required")
class CIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(["make", "-C", str(ROOT / "c"), "page_faults"],
                       capture_output=True, text=True, check=True)

    @staticmethod
    def run_pattern(mode, pattern, mb=1):
        result = subprocess.run([str(C_EXE), "--mode", mode, "--pattern", pattern,
                                 "--mb", str(mb), "--passes", "1"],
                                capture_output=True, text=True, check=True, timeout=25)
        rows = list(csv.DictReader(io.StringIO(result.stdout)))
        assert len(rows) == 1, result.stdout
        return rows[0]

    def test_file_local_mode_visits_hot_and_cold_pages(self):
        import os
        # Independently reconstruct expected page touches, not C's own output.
        page_size = os.sysconf("SC_PAGE_SIZE")
        pages = (1024 * 1024) // page_size
        hot = max(1, pages // 8)
        cold = pages - hot
        def data(page):
            return 1 + page % 251
        expected_local = sum(data(i % hot if i % 10 < 9 or not cold
                                  else hot + (i // 10) % cold) for i in range(pages))
        expected_full = sum(map(data, range(pages)))
        local = self.run_pattern("file", "local")
        sequential = self.run_pattern("file", "sequential")
        random = self.run_pattern("file", "random")
        self.assertEqual(int(local["checksum"]), expected_local)
        self.assertEqual(int(sequential["checksum"]), expected_full)
        self.assertEqual(int(random["checksum"]), expected_full)
        self.assertNotEqual(expected_local, expected_full)
        for row in (local, sequential, random):
            self.assertGreaterEqual(int(row["minor_getrusage"]), 0)
            self.assertGreaterEqual(int(row["major_getrusage"]), 0)
            self.assertGreaterEqual(int(row["minor_proc"]), 0)
            self.assertGreaterEqual(int(row["major_proc"]), 0)

    def test_invalid_pattern_rejected(self):
        proc = subprocess.run([str(C_EXE), "--pattern", "incorrect", "--mb", "1"],
                              capture_output=True, text=True, timeout=10)
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
