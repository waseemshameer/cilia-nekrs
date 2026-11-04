#!/usr/bin/env python3
"""Run before tagging a release; tags never move, so this has to pass first.

  python3 tools/check_release.py vX.Y.Z --gate <commit> --multi <commit> [--commit REV]

--gate is the commit the small4 gate ran on, --multi the commit of the multi-GPU chain, and --commit the commit to be
tagged (default HEAD). Exits 1 and lists every problem:
  CITATION.cff's version and date match the release and its changelog entry;
  CHANGELOG.md has the entry, with Answers, Speed and nekRS lines;
  the listed files at both commits match the release commit;
  a reference.out changed since the last tag comes with 'Answers: changed' in the entry.
"""
import argparse, os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_repo import ANSWERS_CHANGED, REFERENCE, changed_files, commit_exists, listed_match, listed_paths, text


def shown(rev, path):
    out = subprocess.run(["git", "show", "%s:%s" % (rev, path)], capture_output=True)
    return out.stdout.decode(errors="replace") if out.returncode == 0 else ""


def changelog_entry(changelog, tag):
    """(date or None, entry body), or None if the release has no entry. The heading is '## vX.Y.Z (YYYY-MM-DD)'."""
    m = re.search(r"^## %s\b(?:\s*\((\d{4}-\d{2}-\d{2})\))?.*$" % re.escape(tag), changelog, re.M)
    if not m:
        return None
    rest = changelog[m.end():]
    end = re.search(r"^## ", rest, re.M)
    return m.group(1), rest[:end.start()] if end else rest


def check(tag, gate, multi, commit):
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        return ["%s isn't of the form vX.Y.Z" % tag]
    fails = []
    entry = changelog_entry(shown(commit, "CHANGELOG.md"), tag)
    if entry is None:
        fails.append("CHANGELOG.md has no '## %s (date)' entry" % tag)
        date, body = None, ""
    else:
        date, body = entry
        if date is None:
            fails.append("CHANGELOG.md: the %s heading has no (YYYY-MM-DD) date" % tag)
        for line in ("Answers", "Speed", "nekRS"):
            if not re.search(r"^\W*%s\b\W" % line, body, re.M):
                fails.append("CHANGELOG.md: the %s entry has no %s line" % (tag, line))

    citation = shown(commit, "CITATION.cff")
    version = re.search(r"^version:\s*[\"']?([^\s\"']+)", citation, re.M)
    if not version or version.group(1) != tag[1:]:
        fails.append("CITATION.cff: version is %s, not %s" % (version.group(1) if version else "missing", tag[1:]))
    released = re.search(r"^date-released:\s*[\"']?([\d-]+)", citation, re.M)
    if not released:
        fails.append("CITATION.cff: date-released is missing")
    elif date and released.group(1) != date:
        fails.append("CITATION.cff: date-released is %s, the changelog says %s" % (released.group(1), date))

    paths = listed_paths(commit)
    for name, rev in (("--gate", gate), ("--multi", multi)):
        if not commit_exists(rev):
            fails.append("%s %s: no such commit" % (name, rev))
        elif not listed_match(rev, commit, paths):
            fails.append("%s %s: the listed files differ from the release commit" % (name, rev))

    tags = text("tag", "--list", "v*", "--sort=-v:refname", "--merged", commit).split()
    tags = [t for t in tags if t != tag]
    if tags and REFERENCE in changed_files(tags[0], commit) and not ANSWERS_CHANGED.search(body):
        fails.append("%s changed since %s, but the %s entry has no 'Answers: changed' line" % (REFERENCE, tags[0], tag))
    return fails


def main():
    p = argparse.ArgumentParser()
    p.add_argument("tag")
    p.add_argument("--gate", required=True)
    p.add_argument("--multi", required=True)
    p.add_argument("--commit", default="HEAD")
    a = p.parse_args()
    fails = check(a.tag, a.gate, a.multi, a.commit)
    for f in fails:
        print("FAIL  " + f)
    print("release check %s: %s" % (a.tag, "%d failed" % len(fails) if fails else "PASS"))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
