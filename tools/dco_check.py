import re
import subprocess
import sys

SIGNOFF = re.compile(r"^Signed-off-by: .+ <[^<>\s@]+@[^<>\s]+>$", re.MULTILINE)


def git(*args, cwd=None):
    done = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return done.stdout


def missing_signoff(base, head, cwd=None):
    commits = git("rev-list", "--no-merges", f"{base}..{head}", cwd=cwd).split()
    return [sha for sha in commits if not SIGNOFF.search(git("log", "-1", "--format=%B", sha, cwd=cwd))]


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print("usage: dco_check.py <base> <head>", file=sys.stderr)
        return 2
    missing = missing_signoff(*args)
    for sha in missing:
        print(f"missing Signed-off-by: {sha}")
    if missing:
        print("Add the line with `git commit -s` (or `git commit --amend -s` for the last commit).")
        return 1
    print("every commit carries a Signed-off-by line")
    return 0


if __name__ == "__main__":
    sys.exit(main())
