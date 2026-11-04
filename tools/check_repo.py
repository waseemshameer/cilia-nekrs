#!/usr/bin/env python3
"""Repo rules for CI: generic leak patterns, commit author email, file rules and the pull-request gate line.

  python3 tools/check_repo.py [--base REV] [--head REV] [--pr-body-file FILE]

In GitHub Actions the range and pull-request body come from the event, and the options are not needed. Elsewhere the
base defaults to the latest v* tag. A finding names the file and line and never prints the matched text, because CI
logs are public.
"""
import argparse, json, os, re, subprocess, sys

OWN_EMAIL = "45224622+waseemshameer@users.noreply.github.com"
MAX_BYTES = 20_000_000
REFERENCE = "cases/small4/reference.out"
LISTED = "tools/listed_files.txt"
LEAKS = [("home path", re.compile(rb"/home/[A-Za-z]")),
         ("job ID", re.compile(rb"\b(?:jobs?|jobid|slurm)[ _#=:-]*[0-9]{4,}|[_-][0-9]{6,8}\.(?:out|err|log)\b", re.I))]
EMAIL = re.compile(rb"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
ALLOWED_EMAIL = re.compile(rb"noreply@anthropic\.com|.*@users\.noreply\.github\.com", re.I)
LABEL = re.compile(rb"\b(P[0-9]+(\.[0-9]+)+|M\.[0-9]+(\.[0-9]+)*)\b")
GATE_LINE = re.compile(r"^\s*Gate: PASS ([0-9a-f]{7,40})\s*$", re.M)
ANSWERS_CHANGED = re.compile(r"^\W*Answers\W+changed\b", re.I | re.M)


def git(*args, check=True):
    out = subprocess.run(["git", *args], capture_output=True)
    if check and out.returncode:
        sys.exit("git %s: %s" % (" ".join(args), out.stderr.decode(errors="replace").strip()))
    return out.stdout


def text(*args):
    return git(*args).decode(errors="replace")


def commit_exists(rev):
    return subprocess.run(["git", "rev-parse", "-q", "--verify", rev + "^{commit}"], capture_output=True).returncode == 0


def listed_paths(rev):
    """The result-affecting paths, read from the commit being checked."""
    return text("show", "%s:%s" % (rev, LISTED)).split()


def listed_match(a, b, paths):
    return subprocess.run(["git", "diff", "--quiet", a, b, "--", *paths], capture_output=True).returncode == 0


def changed_files(base, head):
    return text("diff", "--no-renames", "--name-only", base, head).split("\n")[:-1] if base else []


def is_listed(path, paths):
    return any(path == p or (p.endswith("/") and path.startswith(p)) for p in paths)


def leak_names(data):
    found = [name for name, rx in LEAKS if rx.search(data)]
    if any(not ALLOWED_EMAIL.fullmatch(m) for m in EMAIL.findall(data)):
        found.append("email")
    return found


def where(data, rx_names):
    """'name line N' for each generic pattern found; binary files have no useful line number."""
    if b"\0" in data[:8000]:
        return list(rx_names)
    lines = data.split(b"\n")
    return ["%s line %d" % (name, next((i + 1 for i, l in enumerate(lines) if name in leak_names(l)), 0))
            for name in rx_names]


def check_tree(head):
    fails = []
    for entry in git("ls-tree", "-r", "-l", "-z", head).split(b"\0")[:-1]:
        meta, path = entry.split(b"\t", 1)
        _, kind, _, size = meta.split()
        path = path.decode(errors="replace")
        if kind != b"blob":
            continue
        if int(size) > MAX_BYTES:
            fails.append("%s: over 20 MB (%d bytes)" % (path, int(size)))
        if path.endswith(".out") and path != REFERENCE:
            fails.append("%s: a run log is tracked; only %s may be" % (path, REFERENCE))
        for name in leak_names(path.encode()):
            fails.append("%s: %s in the file name" % (path, name))
        data = git("cat-file", "blob", "%s:%s" % (head, path))
        for found in where(data, leak_names(data)):
            fails.append("%s: %s" % (path, found))
        if path != REFERENCE and b"\0" not in data[:8000]:   # logs and binaries are not prose
            for i, line in enumerate(data.split(b"\n")):
                if LABEL.search(line):
                    fails.append("%s: old task label, line %d" % (path, i + 1))
    return fails


def check_commits(base, head):
    fails = []
    revs = text("rev-list", "%s..%s" % (base, head) if base else head).split()
    for rev in revs:
        email = text("log", "-1", "--format=%ae", rev).strip()
        name = text("log", "-1", "--format=%an", rev).strip()
        if "waseemshameer" in (name + email).lower() and email != OWN_EMAIL:
            fails.append("commit %s: author email isn't the noreply address" % rev[:8])
        message = git("log", "-1", "--format=%B", rev)
        for found in leak_names(message):
            fails.append("commit %s: %s in the message" % (rev[:8], found))
        if LABEL.search(message):
            fails.append("commit %s: old task label in the message" % rev[:8])
    return fails


def check_reference(base, head):
    changed = changed_files(base, head)
    if REFERENCE not in changed:
        return []
    added = "\n".join(l[1:] for l in text("diff", base, head, "--", "CHANGELOG.md").split("\n") if l.startswith("+"))
    if ANSWERS_CHANGED.search(added):
        return []
    return ["%s changed, but CHANGELOG.md gains no 'Answers: changed' line" % REFERENCE]


def check_gate_line(base, head, body):
    paths = listed_paths(head)
    touched = [f for f in changed_files(base, head) if is_listed(f, paths)]
    if not touched:
        return []
    lines = GATE_LINE.findall(body or "")
    if not lines:
        return ["the pull request changes listed files (%s) but its body has no 'Gate: PASS <commit>' line"
                % ", ".join(touched[:3])]
    gate = lines[-1]
    if not commit_exists(gate):
        return ["'Gate: PASS %s': no such commit" % gate]
    if not listed_match(gate, head, paths):
        return ["'Gate: PASS %s': the listed files at that commit differ from the branch head; rerun the gate" % gate]
    return []


def from_event():
    """(base, head, pull request body or None) from the GitHub Actions event."""
    with open(os.environ["GITHUB_EVENT_PATH"]) as f:
        event = json.load(f)
    if os.environ["GITHUB_EVENT_NAME"] == "pull_request":
        pr = event["pull_request"]
        return pr["base"]["sha"], pr["head"]["sha"], pr["body"] or ""
    before = event.get("before", "")
    if before and set(before) != {"0"} and commit_exists(before):
        return before, event["after"], None
    return ("origin/main" if commit_exists("origin/main") else None), event["after"], None   # a new branch or tag


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base")
    p.add_argument("--head", default="HEAD")
    p.add_argument("--pr-body-file")
    a = p.parse_args()
    body = None
    if os.environ.get("GITHUB_EVENT_PATH") and not a.base:
        base, head, body = from_event()
    else:
        tags = text("tag", "--list", "v*", "--sort=-v:refname", "--merged", a.head).split()
        base, head = a.base or (tags[0] if tags else None), a.head
        if a.pr_body_file:
            with open(a.pr_body_file) as f:
                body = f.read()
    if base:
        base = text("merge-base", base, head).strip()
    fails = check_tree(head) + check_commits(base, head)
    if base:
        fails += check_reference(base, head)
        if body is not None:
            fails += check_gate_line(base, head, body)
    for f in fails:
        print("FAIL  " + f)
    print("repo rules: %s" % ("%d failed" % len(fails) if fails else "PASS"))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
