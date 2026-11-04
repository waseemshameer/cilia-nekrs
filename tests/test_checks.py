#!/usr/bin/env python3
"""tools/check_repo.py and tools/check_release.py: one breaking fixture per rule, each in a throwaway git repo.

Strings that would trip the checks on this file are split in two, so the real tree stays clean with no exemptions.
"""
import json, os, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECK_REPO = os.path.join(ROOT, "tools", "check_repo.py")
CHECK_RELEASE = os.path.join(ROOT, "tools", "check_release.py")
NOREPLY = "45224622+waseemshameer@users.noreply.github.com"
OTHER_EMAIL = "waseemshameer@" + "example.com"
REFERENCE = "cases/small4/reference" + ".out"
ENTRY = "## v1.0.0 (2026-01-02)\n\n**Answers:** unchanged\n**Speed:** same\n**nekRS:** v26.0 96b3cf9e\n"
CITATION = "version: 1.0.0\ndate-released: 2026-01-02\n"


class Repo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name
        self.env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        self.env.pop("GITHUB_EVENT_PATH", None)
        self.git("init", "-q", "-b", "main")
        self.write("cilia.udf", "udf\n")
        self.write("gate.py", "gate\n")
        self.write(REFERENCE, "reference\n")
        self.write("README.md", "readme\n")
        self.write("CHANGELOG.md", "# Changelog\n")
        self.write("CITATION.cff", "version: 0.9.0\ndate-released: 2025-01-01\n")
        self.write("tools/listed_files.txt", "cilia.udf\ngate.py\ncases/\npatches/\n")
        self.commit("start")
        self.git("tag", "v0.9.0")

    def git(self, *args, env=None):
        r = subprocess.run(["git", *args], cwd=self.dir, env={**self.env, **(env or {})},
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def write(self, path, content):
        full = os.path.join(self.dir, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as f:
            f.write(content if isinstance(content, bytes) else content.encode())

    def commit(self, message="change", name="waseemshameer", email=NOREPLY):
        who = {"GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email,
               "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": email}
        self.git("add", "-A", "-f")
        self.git("commit", "-q", "--allow-empty", "-m", message, env=who)
        return self.git("rev-parse", "HEAD")


class RepoRules(Repo):
    def run_check(self, *args, env=None):
        return subprocess.run([sys.executable, CHECK_REPO, "--base", "v0.9.0", *args], cwd=self.dir,
                              env={**self.env, **(env or {})}, capture_output=True, text=True)

    def assert_blocks(self, text, *args):
        r = self.run_check(*args)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn(text, r.stdout)
        return r

    def assert_passes(self, *args):
        r = self.run_check(*args)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_clean_repo_passes(self):
        self.write("README.md", "better readme\n")
        self.commit()
        self.assert_passes()

    def test_home_path(self):
        self.write("README.md", "see /ho" + "me/alice/run\n")
        self.commit()
        self.assert_blocks("README.md: home path line 1")

    def test_home_path_in_binary(self):
        self.write("docs/a.pdf", b"\0\0 /ho" + b"me/alice/fig \0")
        self.commit()
        self.assert_blocks("docs/a.pdf: home path")

    def test_email(self):
        self.write("README.md", "ok\nwrite to alice@" + "example.org\n")
        self.commit()
        self.assert_blocks("README.md: email line 2")

    def test_job_id(self):
        for text in ("jo" + "b 303937", "slu" + "rm-303937", "run_303" + "937.err"):
            self.write("README.md", text + "\n")
            self.commit()
            self.assert_blocks("README.md: job ID line 1")

    def test_ordinary_numbers_are_not_job_ids(self):
        self.write("README.md", "76,800 elements, 303937 points, 2 jobs\n")
        self.commit()
        self.assert_passes()

    def test_leak_in_file_name(self):
        self.write("alice@" + "example.org.txt", "x\n")
        self.commit()
        self.assert_blocks("in the file name")

    def test_leak_in_commit_message(self):
        self.commit("from /ho" + "me/alice/run")
        self.assert_blocks("home path in the message")

    def test_finding_does_not_print_the_match(self):
        self.write("README.md", "alice@" + "example.org\n")
        self.commit()
        self.assertNotIn("alice", self.assert_blocks("email").stdout)

    def test_label_pattern(self):
        for label in ("P" + "3.2", "P" + "3.2.1", "M" + ".10"):
            self.write("cilia.udf", "// %s: reason\n" % label)
            self.commit()
            self.assert_blocks("cilia.udf: old task label, line 1")

    def test_label_in_commit_message(self):
        self.commit("finish P" + "3.2")
        self.assert_blocks("old task label in the message")

    def test_label_lookalikes_pass(self):
        self.write("README.md", "P3 and M10, np.5, N_p 40, 1.5\n")
        self.commit()
        self.assert_passes()

    def test_claude_coauthor_address_allowed(self):
        self.commit("change\n\nCo-Authored-By: Claude <noreply@" + "anthropic.com>")
        self.assert_passes()

    def test_own_commit_needs_noreply(self):
        self.commit(email=OTHER_EMAIL)
        self.assert_blocks("author email isn't the noreply address")

    def test_outside_contributor_email_allowed(self):
        self.commit(name="Alice", email="alice@" + "example.org")
        self.assert_passes()

    def test_old_commits_are_not_rechecked(self):
        self.commit(email=OTHER_EMAIL)
        self.git("tag", "v0.9.1")
        self.commit()
        r = subprocess.run([sys.executable, CHECK_REPO, "--base", "v0.9.1"], cwd=self.dir, env=self.env,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_file_over_20_mb(self):
        self.write("cases/big.re2", b"\0" * (20_000_000 + 1))
        self.commit()
        self.assert_blocks("cases/big.re2: over 20 MB")

    def test_file_of_exactly_20_mb_passes(self):
        self.write("cases/big.re2", b"\0" * 20_000_000)
        self.commit()
        self.assert_passes()

    def test_tracked_run_log(self):
        self.write("cases/small4/run" + ".out", "log\n")
        self.commit()
        self.assert_blocks("a run log is tracked")

    def test_reference_change_needs_answers_changed(self):
        self.write(REFERENCE, "new reference\n")
        self.commit()
        self.assert_blocks("no 'Answers: changed' line")

    def test_reference_change_with_answers_unchanged_fails(self):
        self.write(REFERENCE, "new reference\n")
        self.write("CHANGELOG.md", "# Changelog\n\n**Answers:** unchanged\n")
        self.commit()
        self.assert_blocks("no 'Answers: changed' line")

    def test_reference_change_with_answers_changed_passes(self):
        self.write(REFERENCE, "new reference\n")
        self.write("CHANGELOG.md", "# Changelog\n\n**Answers:** changed, because of X\n")
        self.commit()
        self.assert_passes()

    def body(self, text):
        path = os.path.join(self.dir, "..", os.path.basename(self.dir) + ".body")
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        with open(path, "w") as f:
            f.write(text)
        return "--pr-body-file", path

    def test_missing_gate_line_names_it(self):
        self.write("cilia.udf", "changed\n")
        self.commit()
        self.assert_blocks("no 'Gate: PASS <commit>' line", *self.body("A change."))

    def test_gate_line_needed_for_files_under_a_listed_folder(self):
        self.write("patches/one.patch", "x\n")
        self.commit()
        self.assert_blocks("no 'Gate: PASS <commit>' line", *self.body(""))

    def test_gate_line_not_needed_without_listed_files(self):
        self.write("README.md", "changed\n")
        self.commit()
        self.assert_passes(*self.body("Docs only."))

    def test_gate_line_at_head_passes(self):
        self.write("cilia.udf", "changed\n")
        head = self.commit()
        self.assert_passes(*self.body("Text\r\nGate: PASS %s\r\nMore" % head[:10]))

    def test_gate_line_survives_a_docs_commit(self):
        self.write("cilia.udf", "changed\n")
        gate = self.commit()
        self.write("README.md", "changed\n")
        self.commit()
        self.assert_passes(*self.body("Gate: PASS " + gate))

    def test_push_after_the_gate_fails(self):
        self.write("cilia.udf", "changed\n")
        gate = self.commit()
        self.write("cilia.udf", "changed again\n")
        self.commit()
        self.assert_blocks("differ from the branch head", *self.body("Gate: PASS " + gate))

    def test_gate_line_with_unknown_commit(self):
        self.write("cilia.udf", "changed\n")
        self.commit()
        self.assert_blocks("no such commit", *self.body("Gate: PASS 0123456789"))

    def run_event(self, name, event):
        path = os.path.join(self.dir, "..", os.path.basename(self.dir) + ".json")
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        with open(path, "w") as f:
            json.dump(event, f)
        env = {"GITHUB_EVENT_NAME": name, "GITHUB_EVENT_PATH": path}
        return subprocess.run([sys.executable, CHECK_REPO], cwd=self.dir, env={**self.env, **env},
                              capture_output=True, text=True)

    def test_pull_request_event(self):
        base = self.git("rev-parse", "HEAD")
        self.write("cilia.udf", "changed\n")
        head = self.commit()
        pr = {"base": {"sha": base}, "head": {"sha": head}}
        r = self.run_event("pull_request", {"pull_request": {**pr, "body": None}})
        self.assertEqual(r.returncode, 1)
        self.assertIn("Gate: PASS <commit>", r.stdout)
        r = self.run_event("pull_request", {"pull_request": {**pr, "body": "Gate: PASS " + head}})
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_push_event_checks_the_pushed_commits_and_needs_no_gate_line(self):
        before = self.git("rev-parse", "HEAD")
        self.write("cilia.udf", "changed\n")
        after = self.commit(email=OTHER_EMAIL)
        r = self.run_event("push", {"before": before, "after": after})
        self.assertEqual(r.returncode, 1)
        self.assertIn("author email", r.stdout)
        self.assertNotIn("Gate: PASS", r.stdout)

    def test_new_branch_push_event(self):
        self.write("README.md", "changed\n")
        after = self.commit()
        r = self.run_event("push", {"before": "0" * 40, "after": after})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)   # no origin/main here, so every commit is checked
        self.write("README.md", "changed again\n")
        after = self.commit(email=OTHER_EMAIL)
        r = self.run_event("push", {"before": "0" * 40, "after": after})
        self.assertEqual(r.returncode, 1)
        self.assertIn("author email", r.stdout)


class Release(Repo):
    def good(self, entry=ENTRY, citation=CITATION):
        self.write("CHANGELOG.md", "# Changelog\n\n" + entry + "\n## v0.9.0 (2025-01-01)\n\n**Speed:** old\n")
        self.write("CITATION.cff", citation)
        return self.commit("release")

    def run_check(self, gate, multi=None, tag="v1.0.0"):
        return subprocess.run([sys.executable, CHECK_RELEASE, tag, "--gate", gate, "--multi", multi or gate],
                              cwd=self.dir, env=self.env, capture_output=True, text=True)

    def assert_blocks(self, text, gate, multi=None, tag="v1.0.0"):
        r = self.run_check(gate, multi, tag)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn(text, r.stdout)

    def test_good_release_passes(self):
        head = self.good()
        r = self.run_check(head)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_gate_run_before_a_docs_commit_still_passes(self):
        self.write("cilia.udf", "changed\n")
        gate = self.commit()
        self.good()
        r = self.run_check(gate)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_citation_version(self):
        self.assert_blocks("CITATION.cff: version is 0.9.0", self.good(citation="version: 0.9.0\ndate-released: 2026-01-02\n"))

    def test_citation_date(self):
        self.assert_blocks("date-released is 2025-01-01", self.good(citation="version: 1.0.0\ndate-released: 2025-01-01\n"))

    def test_citation_date_missing(self):
        self.assert_blocks("date-released is missing", self.good(citation="version: 1.0.0\n"))

    def test_changelog_entry_missing(self):
        self.assert_blocks("no '## v1.0.0 (date)' entry", self.good(entry=""))

    def test_changelog_entry_without_date(self):
        self.assert_blocks("heading has no (YYYY-MM-DD) date", self.good(entry=ENTRY.replace(" (2026-01-02)", "")))

    def test_each_changelog_line(self):
        for line, kept in (("Answers", "**Speed:** s\n**nekRS:** n\n"), ("Speed", "**Answers:** a\n**nekRS:** n\n"),
                           ("nekRS", "**Answers:** a\n**Speed:** s\n")):
            head = self.good(entry="## v1.0.0 (2026-01-02)\n\n" + kept)
            self.assert_blocks("has no %s line" % line, head)

    def test_line_in_an_older_entry_does_not_count(self):
        head = self.good(entry="## v1.0.0 (2026-01-02)\n\n**Answers:** a\n**nekRS:** n\n")
        self.assert_blocks("has no Speed line", head)

    def test_gate_commit_differs(self):
        old = self.git("rev-parse", "HEAD")
        self.write("cilia.udf", "changed\n")
        head = self.good()
        self.assert_blocks("--gate", old, head)

    def test_multi_commit_differs(self):
        old = self.git("rev-parse", "HEAD")
        self.write("gate.py", "changed\n")
        head = self.good()
        self.assert_blocks("--multi", head, old)

    def test_unknown_commit(self):
        self.good()
        self.assert_blocks("no such commit", "0123456789")

    def test_reference_changed_needs_answers_changed(self):
        self.write(REFERENCE, "new\n")
        self.assert_blocks("no 'Answers: changed' line", self.good())

    def test_reference_changed_with_answers_changed_passes(self):
        self.write(REFERENCE, "new\n")
        head = self.good(entry=ENTRY.replace("unchanged", "changed, because of X"))
        r = self.run_check(head)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_bad_tag(self):
        self.assert_blocks("isn't of the form", self.good(), tag="1.0")


if __name__ == "__main__":
    unittest.main()
