import unittest

import support
import twno_writer as w
from support import decode, document, props_of, slots_of
from twno_writer import NONE, Document, Obj, RawId, WriteError


class HandNumberingTest(unittest.TestCase):
    def test_slots_match_numbers_computed_by_hand(self):
        doc = document()
        artboard = doc.add(Obj("Artboard", name="A"))
        node = doc.add(Obj("Node", name="n", parent=artboard))
        doc.add(Obj("ScriptInputNumber"))
        doc.add(Obj("ScriptInputNumber", parent=artboard))
        doc.add(Obj("ScriptInputNumber", parent=node))
        doc.add(Obj("ScriptInputNumber", parent="n"))
        doc.add(Obj("ElasticScrollPhysics"))
        doc.add(Obj("KeyboardInput"))
        doc.add(Obj("CubicEaseInterpolator"))
        doc.add(Obj("Node"))
        doc.add(Obj("LinearAnimation", name="a"))
        doc.add(Obj("KeyedObject", object=node))
        doc.add(Obj("StateMachine", name="m"))
        expected = [None, 0, 1, None, None, 2, 3, None, 4, 5, 6, None, None, None]
        self.assertEqual(slots_of(doc), expected)
        self.assertEqual([o.slot for o in doc.objects], expected)

    def test_script_input_named_like_an_artboard_elsewhere(self):
        doc = document()
        doc.add(Obj("Artboard", name="X"))
        doc.add(Obj("Artboard", name="B"))
        doc.add(Obj("Node", name="X"))
        doc.add(Obj("ScriptInputNumber", parent="X"))
        last = doc.add(Obj("Node"))
        decoded = decode(doc)
        self.assertEqual([slot for _, _, slot in decoded], [None, 0, 0, 1, 2, 3])
        self.assertEqual(decoded[4][1]["parentId"], 1)
        self.assertEqual(last.slot, 3)

    def test_script_input_parented_to_artboard_by_name(self):
        doc = document()
        doc.add(Obj("Artboard", name="Only"))
        doc.add(Obj("ScriptInputNumber", parent="Only"))
        doc.add(Obj("Node"))
        self.assertEqual(slots_of(doc), [None, 0, None, 1])


class IndexReferenceTest(unittest.TestCase):
    def machine_document(self):
        doc = document()
        doc.add(Obj("Artboard", name="A"))
        doc.add(Obj("LinearAnimation", name="first"))
        doc.add(Obj("LinearAnimation", name="second"))
        third = doc.add(Obj("LinearAnimation", name="third"))
        doc.add(Obj("StateMachine", name="m0"))
        doc.add(Obj("StateMachineBool", name="a"))
        doc.add(Obj("StateMachineNumber", name="b"))
        trigger = doc.add(Obj("StateMachineTrigger", name="c"))
        doc.add(Obj("StateMachineLayer", name="L"))
        doc.add(Obj("EntryState"))
        doc.add(Obj("AnimationState", animation=third))
        return doc, trigger

    def test_animation_and_input_indices(self):
        doc, trigger = self.machine_document()
        doc.add(Obj("StateTransition"))
        doc.add(Obj("TransitionTriggerCondition", input=trigger))
        doc.add(Obj("TransitionNumberCondition", input="b", opValue=1))
        self.assertEqual(props_of(doc, "AnimationState")["animationId"], 2)
        self.assertEqual(props_of(doc, "TransitionTriggerCondition")["inputId"], 2)
        self.assertEqual(props_of(doc, "TransitionNumberCondition")["inputId"], 1)

    def test_transition_state_index_counts_every_layer_state(self):
        doc, _ = self.machine_document()
        target = doc.add(Obj("AnimationState", animation="first"))
        doc.add(Obj("StateTransition", stateTo=target))
        self.assertEqual(props_of(doc, "StateTransition")["stateToId"], 2)

    def test_condition_of_the_wrong_input_type(self):
        doc, trigger = self.machine_document()
        doc.add(Obj("StateTransition"))
        doc.add(Obj("TransitionBoolCondition", input=trigger))
        with self.assertRaisesRegex(WriteError, "StateMachineBool"):
            doc.to_bytes()

    def test_listener_change_of_the_wrong_input_type(self):
        doc, trigger = self.machine_document()
        doc.add(Obj("StateMachineListener"))
        doc.add(Obj("ListenerNumberChange", input=trigger))
        with self.assertRaisesRegex(WriteError, "StateMachineNumber"):
            doc.to_bytes()

    def test_input_written_after_its_condition_is_refused(self):
        doc = document()
        doc.add(Obj("Artboard", name="A"))
        doc.add(Obj("StateMachine", name="m"))
        doc.add(Obj("StateMachineLayer", name="L"))
        doc.add(Obj("EntryState"))
        doc.add(Obj("StateTransition"))
        doc.add(Obj("TransitionBoolCondition", input="late"))
        doc.add(Obj("StateMachineBool", name="late"))
        with self.assertRaisesRegex(WriteError, "before"):
            doc.to_bytes()

    def test_blend_animation_before_its_animation_is_refused(self):
        doc = document()
        doc.add(Obj("Artboard", name="A"))
        doc.add(Obj("StateMachine", name="m"))
        doc.add(Obj("StateMachineLayer", name="L"))
        doc.add(Obj("BlendState1DInput"))
        doc.add(Obj("BlendAnimation1D", animation="later"))
        doc.add(Obj("LinearAnimation", name="later"))
        with self.assertRaisesRegex(WriteError, "before"):
            doc.to_bytes()

    def test_inputs_of_another_state_machine_are_refused(self):
        doc = document()
        doc.add(Obj("Artboard", name="A"))
        doc.add(Obj("StateMachine", name="m0"))
        first = doc.add(Obj("StateMachineBool", name="a"))
        doc.add(Obj("StateMachine", name="m1"))
        doc.add(Obj("StateMachineLayer", name="L"))
        doc.add(Obj("EntryState"))
        doc.add(Obj("StateTransition"))
        doc.add(Obj("TransitionBoolCondition", input=first))
        with self.assertRaisesRegex(WriteError, "another"):
            doc.to_bytes()

    def test_layer_before_any_state_machine(self):
        doc = document()
        doc.add(Obj("Artboard", name="A"))
        doc.add(Obj("StateMachineLayer", name="L"))
        with self.assertRaisesRegex(WriteError, "before any state machine"):
            doc.to_bytes()

    def test_artboard_without_backboard(self):
        doc = Document()
        doc.add(Obj("Artboard", name="A"))
        with self.assertRaisesRegex(WriteError, "Backboard"):
            doc.to_bytes()

    def test_missing_scope_is_reported_as_such(self):
        doc = document()
        doc.add(Obj("Artboard", name="A"))
        doc.add(Obj("StateMachine", name="m"))
        doc.add(Obj("StateTransition", stateTo="x"))
        with self.assertRaisesRegex(WriteError, "outside any layer"):
            doc.to_bytes()

    def test_default_state_machine_index(self):
        doc = document()
        doc.add(Obj("Artboard", name="A", defaultStateMachine="second"))
        doc.add(Obj("StateMachine", name="first"))
        doc.add(Obj("StateMachine", name="second"))
        self.assertEqual(props_of(doc, "Artboard")["defaultStateMachineId"], 1)

    def test_nested_artboard_index_counts_artboards_of_the_file(self):
        doc = document()
        doc.add(Obj("Artboard", name="A"))
        doc.add(Obj("NestedArtboard", name="slot", artboard="B"))
        doc.add(Obj("Artboard", name="B"))
        self.assertEqual(props_of(doc, "NestedArtboard")["artboardId"], 1)


class SpecialValuesTest(unittest.TestCase):
    def test_none_and_raw_id(self):
        doc = document()
        doc.add(Obj("Artboard", name="A"))
        doc.add(Obj("Node", parent=RawId(0)))
        doc.add(Obj("CubicEaseInterpolator"))
        doc.add(Obj("LinearAnimation", name="a"))
        doc.add(Obj("KeyedObject", object=RawId(7)))
        doc.add(Obj("KeyedProperty", propertyKey=13))
        doc.add(Obj("KeyFrameDouble", frame=0, value=1.0, interpolator=NONE))
        self.assertEqual(props_of(doc, "Node")["parentId"], 0)
        self.assertEqual(props_of(doc, "KeyedObject")["objectId"], 7)
        self.assertEqual(props_of(doc, "KeyFrameDouble")["interpolatorId"], 0xFFFFFFFF)

    def test_raw_id_range(self):
        for value in (-1, 2**32, 1.5, True):
            with self.subTest(value=value), self.assertRaises(WriteError):
                RawId(value)

    def test_property_without_reference_rule_takes_only_special_values(self):
        doc = document()
        doc.add(Obj("Artboard", name="A"))
        with self.assertRaisesRegex(WriteError, "no reference kind"):
            doc.add(Obj("StateMachineListenerSingle", event="x"))
        doc.add(Obj("StateMachineListenerSingle", event=RawId(3)))
        doc.add(Obj("StateMachineListenerSingle", event=NONE))
        self.assertEqual(props_of(doc, "StateMachineListenerSingle")["eventId"], 3)


class ReferenceTypeTest(unittest.TestCase):
    def test_parent_must_be_a_container(self):
        doc = document()
        doc.add(Obj("Artboard", name="A"))
        ease = doc.add(Obj("CubicEaseInterpolator"))
        doc.add(Obj("Node", parent=ease))
        with self.assertRaisesRegex(WriteError, "ContainerComponent"):
            doc.to_bytes()

    def test_interpolator_must_be_an_interpolator(self):
        doc = document()
        doc.add(Obj("Artboard", name="A"))
        shape = doc.add(Obj("Shape", parent="A"))
        fill = doc.add(Obj("Fill", parent=shape))
        doc.add(Obj("LinearAnimation", name="a"))
        doc.add(Obj("KeyedObject", object=shape))
        doc.add(Obj("KeyedProperty", propertyKey=13))
        doc.add(Obj("KeyFrameDouble", frame=0, value=1.0, interpolator=fill))
        with self.assertRaisesRegex(WriteError, "KeyFrameInterpolator"):
            doc.to_bytes()

    def test_name_lookup_filters_by_expected_type(self):
        doc = document()
        doc.add(Obj("Artboard", name="A"))
        doc.add(Obj("Node", name="go"))
        event = doc.add(Obj("Event", name="go"))
        doc.add(Obj("StateMachine", name="m"))
        doc.add(Obj("StateMachineFireEvent", event="go"))
        doc.to_bytes()
        self.assertEqual(props_of(doc, "StateMachineFireEvent")["eventId"], event.slot)

    def test_two_events_with_one_name_stay_ambiguous(self):
        doc = document()
        doc.add(Obj("Artboard", name="A"))
        doc.add(Obj("Event", name="go"))
        doc.add(Obj("Event", name="go"))
        doc.add(Obj("StateMachineFireEvent", event="go"))
        with self.assertRaisesRegex(WriteError, "ambiguous"):
            doc.to_bytes()


class RuleTableTest(unittest.TestCase):
    def test_rules_describe_existing_id_properties_and_types(self):
        index = w.SchemaIndex.default()
        kinds = (w.COMPONENT, w.ANIMATION, w.STATE, w.INPUT, w.STATE_MACHINE, w.ARTBOARD)
        for key, (kind, expected, _) in w.ID_RULES.items():
            with self.subTest(key=key):
                self.assertEqual(index.property(key)["fieldType"], "id")
                self.assertIn(kind, kinds)
                if expected is not None:
                    self.assertIn(expected, index.types)
        for source, wanted in w.INPUT_TYPE_FOR_SOURCE.items():
            self.assertIn(source, index.types)
            self.assertTrue(index.descends(wanted, "StateMachineInput"))

    def test_nested_event_property_has_no_rule(self):
        self.assertNotIn(399, w.ID_RULES)


class ExtensionNameTest(unittest.TestCase):
    def test_alias_forms_of_schema_names_are_refused(self):
        doc = Document()
        for name in ("parent", "interpolator", "stateTo"):
            with self.subTest(name=name), self.assertRaises(WriteError):
                doc.declare_property(50500, "uint", name=name)


if __name__ == "__main__":
    unittest.main()
