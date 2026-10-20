import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DRAFT = REPO_ROOT / ".github" / "workflows" / "tests.yml"
AGENTS = REPO_ROOT / "AGENTS.md"
FILTER = re.compile(r"unit_tests\.exe --% (.*)")


def agents_filter():
    for line in AGENTS.read_text(encoding="utf-8").splitlines():
        match = FILTER.search(line)
        if match:
            return match.group(1).strip()
    raise AssertionError("no unit test filter in AGENTS.md")


class WorkflowDraftTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = DRAFT.read_text(encoding="utf-8")

    def test_it_runs_on_push_and_pull_request(self):
        self.assertRegex(self.text, r"(?m)^on:\s*$")
        self.assertRegex(self.text, r"(?m)^  push:")
        self.assertRegex(self.text, r"(?m)^  pull_request:")

    def test_it_is_valid_yaml_with_the_two_jobs(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("pyyaml is not installed")
        data = yaml.safe_load(self.text)
        self.assertEqual(sorted(data["jobs"]), ["fast-tests", "unit-tests"])
        for job in data["jobs"].values():
            self.assertTrue(job["steps"])

    def test_it_does_not_consume_minutes_while_the_repository_is_private(self):
        guard = "if: ${{ !github.event.repository.private }}"
        for job in ("fast-tests", "unit-tests"):
            block = self.text.split(job + ":", 1)[1].split("runs-on:", 1)[0]
            self.assertIn(guard, block, job)

    def test_a_failing_command_in_a_multi_command_step_fails_the_step(self):
        block = self.text.split("- name: Python tests of the tools", 1)[1].split("- name:", 1)[0]
        self.assertIn("shell: bash", block)

    def test_it_does_not_run_on_tag_pushes(self):
        self.assertRegex(self.text, r"(?m)^  push:\n    branches:")

    def test_it_runs_on_windows(self):
        self.assertIn("runs-on: windows-latest", self.text)

    def test_it_uses_the_same_unit_test_filter_as_agents(self):
        self.assertIn(agents_filter(), self.text)

    def test_it_builds_with_the_msc_toolset(self):
        self.assertIn("--toolset=msc", self.text)

    def test_it_has_no_tab_and_no_secret(self):
        self.assertNotIn("\t", self.text)
        self.assertNotIn("secrets.", self.text)

    def test_it_pins_third_party_actions_to_a_version(self):
        for line in self.text.splitlines():
            match = re.search(r"uses:\s*(\S+)", line)
            if match:
                self.assertRegex(match.group(1), r"@v\d+")

    def test_the_python_test_directories_exist(self):
        for directory in re.findall(r"unittest discover -s (\S+)", self.text):
            self.assertTrue((REPO_ROOT / directory).is_dir(), directory)

    def test_the_node_test_files_exist(self):
        for path in re.findall(r"node --test (\S+)", self.text):
            self.assertTrue((REPO_ROOT / path).is_file(), path)

    def test_it_uploads_the_unit_test_log(self):
        self.assertIn("actions/upload-artifact@v", self.text)

    def test_it_sets_a_timeout(self):
        self.assertIn("timeout-minutes:", self.text)

    def test_it_does_not_run_the_heavy_suites(self):
        self.assertNotIn("wasm", self.text.lower().replace("web/", ""))
        self.assertNotIn("npm test", self.text)


if __name__ == "__main__":
    unittest.main()
