import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

PARITY_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PARITY_DIR))

import render_compare

FAKE = [sys.executable, str(Path(__file__).resolve().parent / "fake_goldens.py")]


def entry(path, artboards=("Main",), features=(), sha="0" * 64, group="unit_tests_root"):
    return {
        "path": path,
        "group": group,
        "size": 10,
        "sha256": sha,
        "artboards": list(artboards),
        "state_machines": [],
        "features": list(features),
        "parse_error": None,
    }


class PlanTest(unittest.TestCase):
    def test_one_artboard_gives_one_job_per_instant(self):
        jobs = render_compare.plan_jobs([entry("a.riv")], [0, 15, 60])
        self.assertEqual(
            [(j.rel, j.advance, j.artboard) for j in jobs],
            [("a.riv", 0, None), ("a.riv", 15, None), ("a.riv", 60, None)],
        )

    def test_several_artboards_add_one_job_per_named_artboard(self):
        jobs = render_compare.plan_jobs([entry("a.riv", artboards=("X", "Y"))], [0])
        self.assertEqual([j.artboard for j in jobs], [None, "X", "Y"])

    def test_no_artboard_file_is_still_planned(self):
        jobs = render_compare.plan_jobs([entry("a.riv", artboards=())], [0, 15])
        self.assertEqual(len(jobs), 2)

    def test_artboard_named_default_does_not_collide_with_the_default(self):
        jobs = render_compare.plan_jobs([entry("a.riv", artboards=("default", "Y"))], [0])
        self.assertEqual(len({j.key for j in jobs}), 3)

    def test_duplicate_artboard_names_are_rendered_once(self):
        jobs = render_compare.plan_jobs([entry("a.riv", artboards=("X", "X", "Y"))], [0])
        self.assertEqual([j.artboard for j in jobs], [None, "X", "Y"])

    def test_job_keys_are_unique(self):
        jobs = render_compare.plan_jobs(
            [entry("a.riv", artboards=("X", "Y")), entry("b.riv")], [0, 15]
        )
        keys = [j.key for j in jobs]
        self.assertEqual(len(keys), len(set(keys)))

    def test_instants_must_be_non_negative_integers(self):
        with self.assertRaises(ValueError):
            render_compare.plan_jobs([entry("a.riv")], [-1])


class SampleTest(unittest.TestCase):
    def setUp(self):
        self.files = []
        features = ["vector", "text", "image", "mesh", "state_machine", "layout"]
        for i in range(60):
            self.files.append(
                entry(f"f{i}.riv", features=[features[i % 6]], sha=f"{i * 7919 % 1000:064d}")
            )

    def test_size_and_determinism(self):
        a = render_compare.select_sample(self.files, 20)
        b = render_compare.select_sample(list(reversed(self.files)), 20)
        self.assertEqual(len(a), 20)
        self.assertEqual([e["path"] for e in a], [e["path"] for e in b])

    def test_every_feature_is_covered(self):
        sample = render_compare.select_sample(self.files, 12)
        covered = {f for e in sample for f in e["features"]}
        self.assertEqual(covered, {"vector", "text", "image", "mesh", "state_machine", "layout"})

    def test_sample_larger_than_population(self):
        self.assertEqual(len(render_compare.select_sample(self.files, 500)), 60)


class CampaignTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.repo = self.dir / "repo"
        self.repo.mkdir()
        self.entries = []
        for name, payload in (("one.riv", b"RIVEaaa"), ("two.riv", b"RIVEbbbb")):
            (self.repo / name).write_bytes(payload)
            self.entries.append(entry(name))
        self.saved = {k: os.environ.get(k) for k in ("FAKE_MODE", "FAKE_REQUIRE_SIG")}
        self.addCleanup(self.restore)
        os.environ["FAKE_MODE"] = "stable"
        os.environ.pop("FAKE_REQUIRE_SIG", None)

    def restore(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def run_campaign(self, **kwargs):
        options = dict(
            repo=self.repo,
            entries=self.entries,
            exe_fork=FAKE,
            exe_ref=FAKE,
            work_dir=self.dir / "work",
            instants=[0, 5],
            jobs=2,
            fmt="riv",
        )
        options.update(kwargs)
        return render_compare.run_campaign(**options)

    def test_identical_runtimes(self):
        records = self.run_campaign()
        self.assertEqual(len(records), 4)
        self.assertEqual({r["status"] for r in records}, {"identical"})
        report = render_compare.build_report(records, {})
        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(report["unexplained"], [])

    def test_a_different_fork_is_reported_and_fails(self):
        records = self.run_campaign(env_fork={"FAKE_MODE": "shift"})
        self.assertEqual({r["status"] for r in records}, {"different"})
        report = render_compare.build_report(records, {})
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual(len(report["unexplained"]), 4)

    def test_explained_difference_does_not_fail(self):
        records = self.run_campaign(env_fork={"FAKE_MODE": "shift"})
        explained = {r["key"]: {"status": "different", "reason": "known"} for r in records}
        report = render_compare.build_report(records, explained)
        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(report["summary"]["explained"], 4)

    def test_explanation_does_not_cover_a_change_of_status(self):
        records = self.run_campaign(env_fork={"FAKE_MODE": "fail"})
        explained = {r["key"]: {"status": "different", "reason": "stale"} for r in records}
        report = render_compare.build_report(records, explained)
        self.assertEqual(report["exit_code"], 1)

    def test_plain_string_explanation_is_not_accepted(self):
        records = self.run_campaign(env_fork={"FAKE_MODE": "shift"})
        explained = {r["key"]: "known" for r in records}
        self.assertEqual(render_compare.build_report(records, explained)["exit_code"], 1)

    def test_empty_campaign_fails(self):
        self.assertEqual(render_compare.build_report([], {})["exit_code"], 1)

    def test_failures_by_timeout_or_exception_are_not_equality(self):
        records = self.run_campaign(exe_fork=["no-such-binary-xyz"], exe_ref=["no-such-binary-xyz"])
        self.assertEqual({r["status"] for r in records}, {"both_error"})
        self.assertEqual(render_compare.build_report(records, {})["exit_code"], 1)

    def test_same_failure_on_both_sides_is_equality(self):
        records = self.run_campaign(env_fork={"FAKE_MODE": "fail"}, env_ref={"FAKE_MODE": "fail"})
        self.assertEqual({r["status"] for r in records}, {"same_failure"})
        self.assertEqual(render_compare.build_report(records, {})["exit_code"], 0)

    def test_failure_on_one_side_only_fails(self):
        records = self.run_campaign(env_ref={"FAKE_MODE": "fail"})
        self.assertEqual({r["status"] for r in records}, {"error_b"})
        self.assertEqual(render_compare.build_report(records, {})["exit_code"], 1)

    def test_twno_mode_gives_the_fork_a_twno_signature_and_the_reference_the_riv(self):
        records = self.run_campaign(
            fmt="twno",
            env_fork={"FAKE_REQUIRE_SIG": "TWNR"},
            env_ref={"FAKE_REQUIRE_SIG": "RIVE"},
        )
        self.assertEqual({r["status"] for r in records}, {"identical"})

    def test_riv_mode_gives_both_the_riv(self):
        records = self.run_campaign(
            fmt="riv",
            env_fork={"FAKE_REQUIRE_SIG": "RIVE"},
            env_ref={"FAKE_REQUIRE_SIG": "RIVE"},
        )
        self.assertEqual({r["status"] for r in records}, {"identical"})

    def test_records_carry_key_instant_and_artboard(self):
        records = self.run_campaign(instants=[3])
        self.assertEqual(
            sorted(r["key"] for r in records), ["one.riv@3@default", "two.riv@3@default"]
        )
        self.assertTrue(all(r["advance"] == 3 and r["artboard"] is None for r in records))

    def test_missing_source_is_an_error_record_not_an_exception(self):
        self.entries.append(entry("absent.riv"))
        records = self.run_campaign(instants=[0])
        self.assertEqual(len(records), 3)
        absent = [r for r in records if r["path"] == "absent.riv"][0]
        self.assertEqual(absent["status"], "setup_error")
        self.assertEqual(render_compare.build_report(records, {})["exit_code"], 1)


class CheckpointTest(CampaignTest):
    def checkpoint(self):
        return self.dir / "ckpt" / "records.jsonl"

    def test_every_record_is_appended_to_the_checkpoint(self):
        records = self.run_campaign(checkpoint=self.checkpoint())
        lines = self.checkpoint().read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 4)
        self.assertEqual({json.loads(line)["key"] for line in lines}, {r["key"] for r in records})

    def test_resume_reuses_recorded_results_without_rendering_again(self):
        first = self.run_campaign(checkpoint=self.checkpoint(), env_fork={"FAKE_MODE": "shift"})
        second = self.run_campaign(checkpoint=self.checkpoint())
        self.assertEqual({r["status"] for r in second}, {"different"})
        self.assertEqual([r["key"] for r in second], [r["key"] for r in first])

    def test_resume_renders_only_what_is_missing(self):
        self.run_campaign(checkpoint=self.checkpoint(), env_fork={"FAKE_MODE": "shift"})
        lines = self.checkpoint().read_text(encoding="utf-8").splitlines()
        self.checkpoint().write_text(lines[0] + chr(10), encoding="utf-8")
        records = self.run_campaign(checkpoint=self.checkpoint())
        statuses = sorted(r["status"] for r in records)
        self.assertEqual(statuses, ["different", "identical", "identical", "identical"])
        self.assertEqual(len(self.checkpoint().read_text(encoding="utf-8").splitlines()), 4)

    def test_truncated_last_line_is_ignored(self):
        self.run_campaign(checkpoint=self.checkpoint())
        text = self.checkpoint().read_text(encoding="utf-8").splitlines()
        self.checkpoint().write_text(chr(10).join(text[:2]) + chr(10) + '{"key": "trunc', encoding="utf-8")
        records = self.run_campaign(checkpoint=self.checkpoint())
        self.assertEqual(len(records), 4)
        self.assertEqual({r["status"] for r in records}, {"identical"})

    def test_setup_errors_are_retried_on_resume(self):
        self.entries.append(entry("late.riv"))
        first = self.run_campaign(checkpoint=self.checkpoint(), instants=[0])
        self.assertIn("setup_error", {r["status"] for r in first})
        (self.repo / "late.riv").write_bytes(b"RIVEccc")
        second = self.run_campaign(checkpoint=self.checkpoint(), instants=[0])
        self.assertEqual({r["status"] for r in second}, {"identical"})

    def test_records_outside_the_plan_are_not_returned(self):
        self.run_campaign(checkpoint=self.checkpoint(), instants=[0, 5])
        records = self.run_campaign(checkpoint=self.checkpoint(), instants=[0])
        self.assertEqual(len(records), 2)

    def test_checkpoint_of_another_format_is_not_reused(self):
        self.run_campaign(checkpoint=self.checkpoint(), env_fork={"FAKE_MODE": "shift"})
        records = self.run_campaign(checkpoint=self.checkpoint(), fmt="twno")
        self.assertEqual({r["status"] for r in records}, {"identical"})


class RetestTest(CampaignTest):
    def retest(self, records, fmt="riv", env_fork=None, env_ref=None):
        return render_compare.retest_differences(
            records,
            repo=self.repo,
            exe_fork=FAKE,
            exe_ref=FAKE,
            work_dir=self.dir / "work",
            fmt=fmt,
            env_fork=env_fork,
            env_ref=env_ref,
            timeout=60,
        )

    def ticking(self, name):
        return {"FAKE_MODE": "tick", "FAKE_TICK_FILE": str(self.dir / name)}

    def test_stable_binaries_with_a_real_difference_stay_different(self):
        env_fork = {"FAKE_MODE": "shift"}
        records = self.run_campaign(env_fork=env_fork)
        records = self.retest(records, env_fork=env_fork)
        self.assertEqual({r["status"] for r in records}, {"different"})
        self.assertEqual(render_compare.build_report(records, {})["exit_code"], 1)

    def test_a_fork_that_varies_between_two_runs_is_noise(self):
        env_fork = self.ticking("fork.tick")
        records = self.run_campaign(env_fork=env_fork)
        self.assertEqual({r["status"] for r in records}, {"different"})
        records = self.retest(records, env_fork=env_fork)
        self.assertEqual({r["status"] for r in records}, {"non_deterministic"})
        self.assertEqual({r["repeat"]["fork"] for r in records}, {False})
        self.assertEqual({r["repeat"]["ref"] for r in records}, {True})

    def test_a_reference_that_varies_between_two_runs_is_noise(self):
        env_ref = self.ticking("ref.tick")
        records = self.run_campaign(env_ref=env_ref)
        records = self.retest(records, env_ref=env_ref)
        self.assertEqual({r["status"] for r in records}, {"non_deterministic"})
        self.assertEqual({r["repeat"]["ref"] for r in records}, {False})

    def test_noise_is_listed_apart_and_does_not_fail(self):
        env_fork = self.ticking("fork.tick")
        records = self.retest(self.run_campaign(env_fork=env_fork), env_fork=env_fork)
        report = render_compare.build_report(records, {})
        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(report["summary"]["noise"], 4)
        self.assertEqual(report["summary"]["unexplained"], 0)
        self.assertEqual(len(report["noise"]), 4)

    def test_identical_records_are_not_retested(self):
        records = self.run_campaign()
        retested = self.retest(records)
        self.assertTrue(all("repeat" not in r for r in retested))

    def test_twno_mode_retests_with_a_twno_fork_source(self):
        env_fork = dict(self.ticking("fork.tick"), FAKE_REQUIRE_SIG="TWNR")
        env_ref = {"FAKE_REQUIRE_SIG": "RIVE"}
        records = self.run_campaign(fmt="twno", env_fork=env_fork, env_ref=env_ref)
        records = self.retest(records, fmt="twno", env_fork=env_fork, env_ref=env_ref)
        self.assertEqual({r["status"] for r in records}, {"non_deterministic"})

    def test_an_intermittent_fork_is_noise_even_when_two_repeats_agree(self):
        env_fork = {"FAKE_MODE": "flaky", "FAKE_TICK_FILE": str(self.dir / "flaky.tick")}
        records = self.run_campaign(env_fork=env_fork)
        records = self.retest(records, env_fork=env_fork)
        self.assertEqual({r["status"] for r in records}, {"non_deterministic"})
        self.assertEqual({r["repeat"]["fork"] for r in records}, {False})

    def test_a_failing_repeat_leaves_the_record_different(self):
        records = self.run_campaign(env_fork={"FAKE_MODE": "shift"})
        records = self.retest(records, env_fork={"FAKE_MODE": "fail"})
        self.assertEqual({r["status"] for r in records}, {"different"})
        self.assertEqual({r["repeat"]["fork"] for r in records}, {None})


class BinariesTest(unittest.TestCase):
    def test_default_binaries_follow_the_configuration(self):
        fork, ref = render_compare.default_binaries("release")
        self.assertEqual(fork.parts[-3:], ("out", "release", "goldens.exe"))
        self.assertEqual(ref.parts[-3:], ("out", "release", "goldens.exe"))
        self.assertIn(".ref", ref.parts)
        self.assertNotIn(".ref", fork.parts)

    def test_debug_is_the_default(self):
        fork, ref = render_compare.default_binaries()
        self.assertEqual(fork.parts[-3:], ("out", "debug", "goldens.exe"))
        self.assertEqual(render_compare.DEFAULT_FORK, fork)
        self.assertEqual(render_compare.DEFAULT_REF, ref)

    def test_unknown_configuration_is_refused(self):
        with self.assertRaises(ValueError):
            render_compare.default_binaries("profile")


class ReportTest(unittest.TestCase):
    def test_markdown_lists_non_identical_records(self):
        records = [
            {"key": "a.riv@0@default", "path": "a.riv", "group": "g", "status": "identical",
             "advance": 0, "artboard": None},
            {"key": "b.riv@0@default", "path": "b.riv", "group": "g", "status": "different",
             "advance": 0, "artboard": None, "differing_pixels": 12, "max_channel_diff": 3},
        ]
        report = render_compare.build_report(records, {})
        text = render_compare.render_markdown(report, records, seconds=12.5)
        self.assertIn("b.riv", text)
        self.assertIn("12", text)
        self.assertIn("different", text)
        self.assertNotIn("a.riv@0", text)

    def test_load_explained(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "e.json"
            path.write_text(json.dumps({"a.riv@0@default": "reason"}), encoding="utf-8")
            self.assertEqual(
                render_compare.load_explained(path), {"a.riv@0@default": "reason"}
            )
            self.assertEqual(render_compare.load_explained(Path(tmp) / "absent.json"), {})


if __name__ == "__main__":
    unittest.main()
