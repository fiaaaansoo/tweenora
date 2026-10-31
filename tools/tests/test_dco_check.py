import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

TOOLS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLS_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))

import dco_check

SCRIPT = TOOLS_DIR / "dco_check.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "dco.yml"
SIGNED = "Add a thing\n\nSigned-off-by: Ada Lovelace <ada@example.org>"
UNSIGNED = "Add another thing"


def git(cwd, *args):
    done = subprocess.run(
        ["git", "-c", "user.name=T", "-c", "user.email=t@example.org", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return done.stdout.strip()


class Repo:
    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name)
        git(self.path, "init", "-q", "-b", "main")
        self.commit("base", "initial\n")
        self.base = git(self.path, "rev-parse", "HEAD")

    def cleanup(self):
        self._tmp.cleanup()

    def commit(self, name, message):
        (self.path / f"{name}.txt").write_text(name, encoding="utf-8")
        git(self.path, "add", ".")
        git(self.path, "commit", "-q", "-m", message)
        return git(self.path, "rev-parse", "HEAD")

    def head(self):
        return git(self.path, "rev-parse", "HEAD")


class MissingSignoffCase(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        self.addCleanup(self.repo.cleanup)

    def missing(self):
        return dco_check.missing_signoff(self.repo.base, self.repo.head(), cwd=self.repo.path)

    def test_signed_commits_pass(self):
        self.repo.commit("a", SIGNED)
        self.repo.commit("b", SIGNED)
        self.assertEqual(self.missing(), [])

    def test_unsigned_commit_is_listed(self):
        self.repo.commit("a", SIGNED)
        bad = self.repo.commit("b", UNSIGNED)
        self.assertEqual(self.missing(), [bad])

    def test_every_unsigned_commit_is_listed(self):
        first = self.repo.commit("a", UNSIGNED)
        second = self.repo.commit("b", UNSIGNED)
        self.assertEqual(sorted(self.missing()), sorted([first, second]))

    def test_empty_range_passes(self):
        self.assertEqual(dco_check.missing_signoff(self.repo.base, self.repo.base, cwd=self.repo.path), [])

    def test_sign_off_without_an_address_is_rejected(self):
        bad = self.repo.commit("a", "Add\n\nSigned-off-by: Ada Lovelace")
        self.assertEqual(self.missing(), [bad])

    def test_sign_off_must_be_on_its_own_line(self):
        bad = self.repo.commit("a", "Add Signed-off-by: Ada <ada@example.org> inline")
        self.assertEqual(self.missing(), [bad])

    def test_merge_commits_are_not_required_to_be_signed(self):
        git(self.repo.path, "checkout", "-q", "-b", "side")
        side = self.repo.commit("side", SIGNED)
        git(self.repo.path, "checkout", "-q", "main")
        main = self.repo.commit("main", SIGNED)
        git(self.repo.path, "merge", "-q", "--no-ff", "-m", "Merge side", "side")
        self.assertEqual(self.missing(), [])
        self.assertNotEqual(side, main)


class CommandLineCase(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        self.addCleanup(self.repo.cleanup)

    def run_script(self):
        return subprocess.run(
            [sys.executable, "-I", str(SCRIPT), self.repo.base, self.repo.head()],
            cwd=self.repo.path,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def test_exit_code_is_zero_when_all_commits_are_signed(self):
        self.repo.commit("a", SIGNED)
        self.assertEqual(self.run_script().returncode, 0)

    def test_exit_code_is_one_and_the_commit_is_named_when_one_is_unsigned(self):
        bad = self.repo.commit("a", UNSIGNED)
        done = self.run_script()
        self.assertEqual(done.returncode, 1)
        self.assertIn(bad, done.stdout)
        self.assertIn("git commit -s", done.stdout)


class WorkflowCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.data = yaml.safe_load(cls.text)

    def test_it_runs_on_pull_requests_that_touch_the_editor_or_the_server(self):
        triggers = self.data[True]
        self.assertEqual(list(triggers), ["pull_request"])
        self.assertEqual(sorted(triggers["pull_request"]["paths"]), ["editor/**", "server/**"])

    def test_it_does_not_run_while_the_repository_is_private(self):
        job = next(iter(self.data["jobs"].values()))
        self.assertIn("!github.event.repository.private", str(job["if"]))

    def test_it_calls_the_script_with_the_pull_request_range(self):
        self.assertIn("tools/dco_check.py", self.text)
        self.assertIn("github.event.pull_request.base.sha", self.text)
        self.assertIn("github.event.pull_request.head.sha", self.text)

    def test_the_whole_history_is_fetched_so_the_range_resolves(self):
        job = next(iter(self.data["jobs"].values()))
        checkout = next(step for step in job["steps"] if "actions/checkout" in step.get("uses", ""))
        self.assertEqual(checkout["with"]["fetch-depth"], 0)

    def test_actions_are_pinned_to_a_major_version(self):
        for step in next(iter(self.data["jobs"].values()))["steps"]:
            if "uses" in step:
                self.assertRegex(step["uses"], r"@v\d+$")

    def test_the_pull_request_values_reach_the_shell_through_the_environment(self):
        for line in self.text.splitlines():
            if "dco_check.py" in line:
                self.assertNotIn("${{", line)


if __name__ == "__main__":
    unittest.main()
