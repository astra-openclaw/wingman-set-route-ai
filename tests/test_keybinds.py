from pathlib import Path
import tempfile
import unittest
from support import ROOT
from sra_keybinds import BindError, keyboard_binding, read_bindings

class KeybindTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="sra32-binds-")
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/"actionmaps.xml"

    def test_missing_file_defaults(self):
        self.assertEqual(read_bindings(self.path),{"starmap":("f2",),"plan":("r",)})

    def test_real_layout_modifiers_crlf(self):
        fixture=ROOT/"tests/fixtures/actionmaps.xml"
        self.assertIn(b"\r\n",fixture.read_bytes())
        self.assertEqual(read_bindings(fixture),{"starmap":("right alt","3"),"plan":("left ctrl","r")})

    def test_explicit_unbound_refused(self):
        self.path.write_text('<ActionMaps><ActionProfiles><actionmap name="mapui"><action name="mapui_action_planroute"><rebind input="kb1_ "/></action></actionmap></ActionProfiles></ActionMaps>',encoding="utf-8")
        with self.assertRaisesRegex(BindError,"unbound"): read_bindings(self.path)

    def test_conflicting_maps_refused(self):
        self.path.write_text('<ActionMaps><ActionProfiles><actionmap name="player"><action name="v_starmap"><rebind input="kb1_f3"/></action></actionmap></ActionProfiles></ActionMaps>',encoding="utf-8")
        with self.assertRaisesRegex(BindError,"disagree"): read_bindings(self.path)

    def test_malformed_file_refused(self):
        self.path.write_text('<ActionMaps>',encoding="utf-8")
        with self.assertRaises(BindError): read_bindings(self.path)

    def test_wrong_root_refused(self):
        self.path.write_text('<ActionProfiles/>',encoding="utf-8")
        with self.assertRaises(BindError): read_bindings(self.path)

    def test_unsupported_device_or_key_refused(self):
        for value in ("js1_button2","kb1_unknown","kb1_lalt+",""):
            with self.assertRaises(BindError): keyboard_binding(value)

    def test_joystick_only_keeps_keyboard_defaults(self):
        self.path.write_bytes(b'<ActionMaps>\r\n <ActionProfiles>\r\n  <actionmap name="player"><action name="v_starmap"><rebind input="js1_button5"/></action></actionmap>\r\n </ActionProfiles>\r\n</ActionMaps>')
        self.assertEqual(read_bindings(self.path)["starmap"],("f2",))

    def test_keyboard_plus_joystick_uses_keyboard(self):
        raw=(ROOT/"tests/fixtures/actionmaps.xml").read_bytes()
        raw=raw.replace(b'<rebind input="kb1_ralt+3"/>',b'<rebind input="js1_button5"/><rebind input="kb1_ralt+3"/>')
        self.path.write_bytes(raw)
        self.assertEqual(read_bindings(self.path)["starmap"],("right alt","3"))

    def test_blank_keyboard_names_action_and_numpad_enter_refuses(self):
        for action,map_name,label in (("v_starmap","player","Starmap"),("mapui_action_planroute","mapui","plan route")):
            self.path.write_text(f'<ActionMaps><ActionProfiles><actionmap name="{map_name}"><action name="{action}"><rebind input="kb1_ "/></action></actionmap></ActionProfiles></ActionMaps>',encoding="utf-8")
            with self.assertRaisesRegex(BindError,label+" keyboard action is explicitly unbound"):
                read_bindings(self.path)
        with self.assertRaises(BindError):keyboard_binding("kb1_np_enter")
