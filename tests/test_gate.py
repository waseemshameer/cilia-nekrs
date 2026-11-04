#!/usr/bin/env python3
"""gate.py from the outside: the reference against itself passes; perturbed, cut-short and wrong-SHA logs fail.

reference.out is a trimmed log with no version header, so the temporary copies get one added. Needs numpy.
"""
import os, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GATE = os.path.join(ROOT, "gate.py")
with open(os.path.join(ROOT, "cases", "small4", "reference.out"), errors="replace") as f:
    REFERENCE = f.readlines()
SHA = open(os.path.join(ROOT, "NEKRS_VERSION")).read().split()[1]
HEADER = "v26.0.1 (sha:%s)\n" % SHA


def scaled(lines, tag, column, factor):
    """Multiply one column of the lines ending in `tag`; column 0 is the time."""
    out = []
    for line in lines:
        s = line.split()
        if s and s[-1] == tag:
            s[column] = "%.10e" % (float(s[column]) * factor)
            line = " ".join(s) + "\n"
        out.append(line)
    return out


def ended_at(lines, end):
    """Drop the vals and wall lines after t = end, as in a run that stopped early."""
    def keep(line):
        s = line.split()
        return not (s and s[-1] in ("vals", "wall") and float(s[0]) > end)
    return [line for line in lines if keep(line)]


class Gate(unittest.TestCase):
    def run_gate(self, lines):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "run.log")
            with open(path, "w") as f:
                f.writelines(lines)
            r = subprocess.run([sys.executable, GATE, path], capture_output=True, text=True)
        self.assertNotIn("Traceback", r.stderr)
        return r

    def assert_fails(self, lines, reason):
        r = self.run_gate(lines)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("GATE FAIL", r.stdout)
        self.assertRegex(r.stdout, reason)

    def test_reference_against_itself_passes(self):
        r = self.run_gate([HEADER] + REFERENCE)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("GATE PASS", r.stdout)

    def test_output_names_files_only(self):
        r = self.run_gate([HEADER] + REFERENCE)
        self.assertNotIn(os.sep + "run.log", r.stdout)
        self.assertNotIn(ROOT, r.stdout)

    def test_each_tag_perturbed_fails(self):
        self.assert_fails([HEADER] + scaled(REFERENCE, "vals", 1, 1.01), r"ubar.*FAIL")
        self.assert_fails([HEADER] + scaled(REFERENCE, "wall", 3, 1.01), r"int p \(z=0\.001\).*FAIL")

    def test_vmax_cycle_integral_perturbed_fails(self):
        self.assert_fails([HEADER] + scaled(REFERENCE, "vals", 2, 1.01), r"\|V\|max.*FAIL")

    def test_cut_short_fails(self):
        self.assert_fails([HEADER] + ended_at(REFERENCE, 1.5), r"FAIL \(run ends at t = ")

    def test_wrong_sha_fails(self):
        self.assert_fails(["v26.0.1 (sha:0123abcd)\n"] + REFERENCE, r"nekRS sha: log 0123abcd.*FAIL")

    def test_two_shas_fail(self):
        self.assert_fails([HEADER, "v26.0.1 (sha:0123abcd)\n"] + REFERENCE, r"nekRS sha:.*FAIL")

    def test_no_sha_fails(self):
        self.assert_fails(REFERENCE, r"nekRS sha: log none.*FAIL")


if __name__ == "__main__":
    unittest.main()
