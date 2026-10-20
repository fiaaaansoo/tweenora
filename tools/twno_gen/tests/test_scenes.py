import contextlib
import io
import math
import tempfile
import unittest
from pathlib import Path

import support
import build_examples
import render_check
import scene_kit as kit
from scenes import bouncing_ball, spinning_square
from support import read
from twno_writer import Document, Obj, WriteError

EMPTY_ID = 0xFFFFFFFF
ADVANCE_OFFSET = 1
POSITION_TOLERANCE = 0.6
ANGLE_TOLERANCE = 0.8
COLOR_TOLERANCE = 1.5
MASK_TOLERANCE = 3
MAX_STEP_RATIO = 3.0
MAX_STEP = 14.0
END_TOLERANCE_LEVELS = 12
END_TOLERANCE_PIXELS = 100
TEAL_RGB = ((kit.TEAL >> 16) & 255, (kit.TEAL >> 8) & 255, kit.TEAL & 255)
AMBER_RGB = ((kit.AMBER >> 16) & 255, (kit.AMBER >> 8) & 255, kit.AMBER & 255)
GROUND_RGB = ((kit.GROUND >> 16) & 255, (kit.GROUND >> 8) & 255, kit.GROUND & 255)


def bezier_progress(x1, y1, x2, y2, fraction):
    def axis(a, b, s):
        return 3 * (1 - s) ** 2 * s * a + 3 * (1 - s) * s ** 2 * b + s ** 3

    low, high = 0.0, 1.0
    for _ in range(60):
        middle = (low + high) / 2
        if axis(x1, x2, middle) < fraction:
            low = middle
        else:
            high = middle
    return axis(y1, y2, (low + high) / 2)


def sample(frames, curves, at):
    if at <= frames[0][0]:
        return frames[0][1]
    for (f0, v0, how), (f1, v1, _) in zip(frames, frames[1:]):
        if at <= f1:
            fraction = (at - f0) / (f1 - f0)
            if how is not None:
                fraction = bezier_progress(*curves[how], fraction)
            return v0 + (v1 - v0) * fraction
    return frames[-1][1]


BALL_CURVES = {"in": bouncing_ball.EASE_IN, "out": bouncing_ball.EASE_OUT}
SPIN_CURVES = {"ease": spinning_square.EASE}


def ball_state(at):
    tracks = bouncing_ball.BALL_TRACKS
    return tuple(sample(tracks[name], BALL_CURVES, at) for name in ("y", "scaleX", "scaleY"))


def spin_state(at):
    angle = sample([(f, v, None) for f, v in spinning_square.ROTATION], SPIN_CURVES, at)
    scale = sample([(f, v, "ease") for f, v in spinning_square.SCALE], SPIN_CURVES, at)
    return angle, scale


def channels(color):
    return tuple((color >> shift) & 255 for shift in (16, 8, 0))


def lerp_color(at):
    frames = spinning_square.COLORS
    for (f0, c0), (f1, c1) in zip(frames, frames[1:]):
        if at <= f1:
            fraction = (at - f0) / (f1 - f0)
            return tuple(a + (b - a) * fraction for a, b in zip(channels(c0), channels(c1)))
    return channels(frames[-1][1])


class ScenesAreDeterministicTest(unittest.TestCase):
    def quiet(self, call):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return call()

    def test_regeneration_is_identical(self):
        self.assertEqual(build_examples.render_all(), build_examples.render_all())

    def test_versioned_files_match_the_scenes(self):
        self.assertEqual(build_examples.check(build_examples.DEFAULT_OUT), [])

    def test_check_flags_a_stale_file(self):
        with tempfile.TemporaryDirectory() as folder:
            build_examples.build(folder)
            self.assertEqual(build_examples.check(folder), [])
            stale = Path(folder) / "bouncing-ball.riv"
            stale.write_bytes(stale.read_bytes() + bytes(1))
            self.assertEqual(build_examples.check(folder), ["bouncing-ball.riv"])
            self.assertEqual(self.quiet(lambda: build_examples.main(["--check", "--out", folder])), 1)
            self.assertEqual(self.quiet(lambda: build_examples.main(["--out", folder])), 0)
            self.assertEqual(self.quiet(lambda: build_examples.main(["--check", "--out", folder])), 0)

    def test_missing_file_is_stale(self):
        with tempfile.TemporaryDirectory() as folder:
            expected = sorted(scene.NAME + ".riv" for scene in build_examples.SCENES)
            self.assertEqual(sorted(build_examples.check(folder)), expected)


class SceneStructureTest(unittest.TestCase):
    def load(self, scene):
        return read(scene.build().to_bytes(b"RIVE"))

    def objects(self, document, type_name):
        return [o for o in document["objects"] if o["typeName"] == type_name]

    def prop(self, obj, name, default=None):
        return next((p["value"] for p in obj["properties"] if p["name"] == name), default)

    def check_scene(self, scene, targets):
        document = self.load(scene)
        by_slot = {o["slot"]: o for o in document["objects"] if o["slot"] is not None}
        animations = self.objects(document, "LinearAnimation")
        self.assertEqual(len(animations), 1)
        self.assertEqual(self.prop(animations[0], "duration"), scene.DURATION)
        self.assertEqual(self.prop(animations[0], "fps"), scene.FPS)
        self.assertEqual(self.prop(animations[0], "loopValue"), 1)
        keyed = [by_slot[self.prop(o, "objectId")]["name"] for o in self.objects(document, "KeyedObject")]
        self.assertEqual(keyed, targets)
        for frame in self.objects(document, "KeyFrameDouble") + self.objects(document, "KeyFrameColor"):
            interpolator = self.prop(frame, "interpolatorId", EMPTY_ID)
            if interpolator != EMPTY_ID:
                self.assertEqual(by_slot[interpolator]["typeName"], "CubicEaseInterpolator")
            self.assertLessEqual(self.prop(frame, "frame"), scene.DURATION)
        self.assertEqual([self.prop(m, "name") for m in self.objects(document, "StateMachine")], [scene.MACHINE])
        self.assertEqual(self.prop(self.objects(document, "Artboard")[0], "defaultStateMachineId"), 0)
        names = [o["typeName"] for o in document["objects"]]
        start = names.index("EntryState")
        self.assertEqual(
            names[start : start + 5],
            ["EntryState", "StateTransition", "AnyState", "ExitState", "AnimationState"],
        )
        self.assertEqual(self.prop(document["objects"][start + 1], "stateToId"), 3)
        self.assertEqual(self.prop(document["objects"][start + 4], "animationId"), 0)
        return document

    def test_bouncing_ball(self):
        document = self.check_scene(bouncing_ball, ["ball", "shadow"])
        shapes = [o["name"] for o in self.objects(document, "Shape")]
        self.assertEqual(shapes, ["highlight", "body", "shadow", "floor"])

    def test_spinning_square(self):
        document = self.check_scene(spinning_square, ["pivot", "square color"])
        self.assertEqual([o["name"] for o in self.objects(document, "Shape")], ["mark", "square"])

    def test_ball_curves_are_attached_to_the_right_segments(self):
        document = self.load(bouncing_ball)
        by_slot = {o["slot"]: o for o in document["objects"] if o["slot"] is not None}
        first = self.objects(document, "KeyedProperty")[0]
        frames = []
        for obj in document["objects"][document["objects"].index(first) + 1 :]:
            if obj["typeName"] != "KeyFrameDouble":
                break
            frames.append(obj)

        def rounded(values):
            return tuple(float(f"{v:.6g}") for v in values)

        curves = {}
        for frame in frames:
            curve_id = self.prop(frame, "interpolatorId", EMPTY_ID)
            if curve_id != EMPTY_ID:
                curve = by_slot[curve_id]
                curves[self.prop(frame, "frame")] = rounded(self.prop(curve, n) for n in ("x1", "y1", "x2", "y2"))
        expected = {0: rounded(bouncing_ball.EASE_IN), bouncing_ball.CONTACT_OUT: rounded(bouncing_ball.EASE_OUT)}
        self.assertEqual(curves, expected)

    def test_ball_falls_then_rises_without_a_jump(self):
        positions = [ball_state(f)[0] for f in range(bouncing_ball.DURATION + 1)]
        steps = [b - a for a, b in zip(positions, positions[1:])]
        fall = steps[: bouncing_ball.CONTACT_IN]
        rise = steps[bouncing_ball.CONTACT_OUT :]
        self.assertTrue(all(step >= 0 for step in fall))
        self.assertTrue(all(step <= 0 for step in rise))
        self.assertGreater(fall[-1], fall[0])
        self.assertGreater(rise[-1], rise[0])
        for step in steps:
            self.assertLess(abs(step), MAX_STEP)
        for segment in (fall, rise):
            for step, following in zip(segment, segment[1:]):
                if abs(step) > 1.0 and abs(following) > 1.0:
                    ratio = max(abs(step), abs(following)) / min(abs(step), abs(following))
                    self.assertLess(ratio, MAX_STEP_RATIO)

    def test_every_track_is_ordered_and_loops_without_a_jump(self):
        tracks = list(bouncing_ball.BALL_TRACKS.values()) + [bouncing_ball.SHADOW_SCALES]
        tracks += [
            [(f, v, None) for f, v in track]
            for track in (spinning_square.SCALE, spinning_square.COLORS)
        ]
        for track in tracks:
            frames = [f for f, _, _ in track]
            self.assertEqual(frames, sorted(set(frames)))
            self.assertEqual(frames[0], 0)
        for track in list(bouncing_ball.BALL_TRACKS.values()) + [bouncing_ball.SHADOW_SCALES]:
            self.assertEqual(track[0][1], track[-1][1])
            self.assertEqual(track[-1][0], bouncing_ball.DURATION)
        self.assertEqual(spinning_square.SCALE[0][1], spinning_square.SCALE[-1][1])
        self.assertEqual(spinning_square.COLORS[0][1], spinning_square.COLORS[-1][1])
        self.assertAlmostEqual(spinning_square.ROTATION[-1][1] - spinning_square.ROTATION[0][1], 2 * math.pi)

    def assert_state(self, actual, expected):
        for measured, wanted in zip(actual, expected):
            self.assertAlmostEqual(measured, wanted, places=4)

    def test_expected_values_match_the_keyframes(self):
        self.assert_state(ball_state(0), (bouncing_ball.APEX_Y, 1.0, 1.0))
        self.assert_state(ball_state(bouncing_ball.CONTACT_IN), (bouncing_ball.CONTACT_Y, 1.0, 1.0))
        self.assert_state(
            ball_state(bouncing_ball.SQUASH),
            (bouncing_ball.SQUASH_Y, bouncing_ball.SQUASH_SCALE_X, bouncing_ball.SQUASH_SCALE_Y),
        )
        self.assert_state(ball_state(bouncing_ball.DURATION), ball_state(0))
        early = ball_state(bouncing_ball.CONTACT_IN / 2)[0]
        self.assertLess(early, (bouncing_ball.APEX_Y + bouncing_ball.CONTACT_Y) / 2)
        angle, scale = spin_state(spinning_square.HALF)
        self.assertAlmostEqual(angle, math.pi)
        self.assertAlmostEqual(scale, spinning_square.SCALE_LOW)
        self.assert_state(lerp_color(spinning_square.DURATION), channels(kit.TEAL))

    def test_keying_a_text_property_is_refused_without_touching_the_document(self):
        doc = Document()
        node = doc.add(Obj("Node", name="n"))
        before = len(doc.objects)
        with self.assertRaises(WriteError):
            kit.animate(doc, node, {"x": [(0, 1.0, None)], "name": [(0, "a", None)]})
        with self.assertRaises(WriteError):
            kit.animate(doc, node, {"nope": [(0, 1.0, None)]})
        self.assertEqual(len(doc.objects), before)

    def test_one_shot_copy_has_the_loop_value_zero(self):
        document = read(bouncing_ball.build(loop=0).to_bytes(b"RIVE"))
        self.assertEqual(self.prop(self.objects(document, "LinearAnimation")[0], "loopValue"), 0)


def frame_of(time_frames):
    return time_frames + ADVANCE_OFFSET


def mask(image, rgb, tolerance=MASK_TOLERANCE):
    numpy, _ = render_check.require_imaging()
    close = numpy.abs(image[:, :, :3].astype(int) - numpy.array(rgb)).max(axis=2) <= tolerance
    return close & (image[:, :, 3] == 255)


def pixels_of(selection, size):
    numpy, _ = render_check.require_imaging()
    ys, xs = numpy.where(selection)
    if not len(ys):
        raise AssertionError("no pixel of the expected color in the render")
    scale = render_check.FRAME_SIZE / size
    return xs / scale, ys / scale


def extent(selection, size):
    xs, ys = pixels_of(selection, size)
    return xs.min(), xs.max(), ys.min(), ys.max()


def centroid(selection, size):
    xs, ys = pixels_of(selection, size)
    return xs.mean(), ys.mean()


class NativeSceneRenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            render_check.find_goldens()
            render_check.require_imaging()
        except render_check.RenderUnavailable as error:
            raise unittest.SkipTest(str(error)) from None
        cls.folder = tempfile.TemporaryDirectory()
        cls.scenes = {scene.NAME: scene for scene in (bouncing_ball, spinning_square)}
        cls.counter = 0

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def render(self, name, time_frames, suffix=".riv", **build_args):
        NativeSceneRenderTest.counter += 1
        document = self.scenes[name].build(**build_args)
        signature = b"RIVE" if suffix == ".riv" else b"TWNR"
        path = Path(self.folder.name) / f"{name}-{self.counter}{suffix}"
        path.write_bytes(document.to_bytes(signature))
        return render_check.render(path, advance=frame_of(time_frames))

    def test_ball_bottom_edge_follows_the_keyframes(self):
        size = bouncing_ball.SIZE
        for at in (0, 24, 42, 48, 54, 72, bouncing_ball.DURATION):
            with self.subTest(frame=at):
                y, scale_x, scale_y = ball_state(at)
                image = self.render(bouncing_ball.NAME, at)
                left, right, _, bottom = extent(mask(image, TEAL_RGB), size)
                self.assertAlmostEqual(bottom, y + bouncing_ball.RADIUS * scale_y, delta=POSITION_TOLERANCE)
                self.assertAlmostEqual((left + right) / 2, size / 2, delta=POSITION_TOLERANCE)
                hidden = render_check.hidden_rows(image) / (render_check.FRAME_SIZE / size)
                if y > hidden + 1:
                    expected_width = 2 * bouncing_ball.RADIUS * scale_x
                    self.assertAlmostEqual(right - left, expected_width, delta=POSITION_TOLERANCE)

    def test_ball_touches_the_drawn_floor_at_the_squash(self):
        size = bouncing_ball.SIZE
        image = self.render(bouncing_ball.NAME, bouncing_ball.SQUASH)
        floor_top = extent(mask(image, GROUND_RGB), size)[2]
        ball_bottom = extent(mask(image, TEAL_RGB), size)[3]
        self.assertAlmostEqual(floor_top, bouncing_ball.FLOOR_TOP, delta=POSITION_TOLERANCE)
        self.assertAlmostEqual(ball_bottom, floor_top, delta=POSITION_TOLERANCE)
        apex = extent(mask(self.render(bouncing_ball.NAME, 0), TEAL_RGB), size)
        self.assertLess(apex[3], floor_top - 150)

    def test_a_one_shot_ball_ends_on_the_first_frame(self):
        start = self.render(bouncing_ball.NAME, 0)
        end = self.render(bouncing_ball.NAME, bouncing_ball.DURATION + 3, loop=0)
        self.assertTrue((start == end).all())

    def test_a_one_shot_square_ends_on_the_first_frame(self):
        numpy, _ = render_check.require_imaging()
        start = self.render(spinning_square.NAME, 0)
        end = self.render(spinning_square.NAME, spinning_square.DURATION + 3, loop=0)
        difference = numpy.abs(start.astype(int) - end.astype(int)).max(axis=2)
        self.assertLessEqual(int(difference.max()), END_TOLERANCE_LEVELS)
        self.assertLessEqual(int((difference > 0).sum()), END_TOLERANCE_PIXELS)

    def test_twno_renders_like_riv(self):
        riv = self.render(bouncing_ball.NAME, bouncing_ball.SQUASH)
        twno = self.render(bouncing_ball.NAME, bouncing_ball.SQUASH, ".twno")
        self.assertTrue((riv == twno).all())

    def test_square_mark_turns_with_the_rotation(self):
        size = spinning_square.SIZE
        quarter = spinning_square.DURATION // 4
        for at in (0, quarter, 2 * quarter, 3 * quarter, spinning_square.DURATION):
            with self.subTest(frame=at):
                angle, scale = spin_state(at)
                image = self.render(spinning_square.NAME, at)
                x, y = centroid(mask(image, AMBER_RGB), size)
                half = size / 2
                measured = math.degrees(math.atan2(y - half, x - half))
                difference = (measured - math.degrees(angle) + 180) % 360 - 180
                self.assertLess(abs(difference), ANGLE_TOLERANCE)
                distance = math.hypot(x - half, y - half)
                self.assertAlmostEqual(distance, spinning_square.MARK_OFFSET * scale, delta=POSITION_TOLERANCE)

    def test_square_color_follows_the_keyframes(self):
        for at in (0, 15, spinning_square.HALF, 90, spinning_square.DURATION):
            with self.subTest(frame=at):
                image = self.render(spinning_square.NAME, at)
                centre = image[render_check.FRAME_SIZE // 2, render_check.FRAME_SIZE // 2, :3]
                for measured, expected in zip(centre, lerp_color(at)):
                    self.assertAlmostEqual(int(measured), expected, delta=COLOR_TOLERANCE)


if __name__ == "__main__":
    unittest.main()
