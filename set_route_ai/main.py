import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, List
from services.benchmark import Benchmark
import ctypes
import ctypes.wintypes
from skills.skill_base import Skill
from api.interface import (
    SkillConfig,
    SettingsConfig,
)
from api.enums import LogType
from destination_engine import DestinationPhoneticEngine

if TYPE_CHECKING:
    from wingmen.wingman_context import WingmanContext


CALIBRATION_FILE = "mouse_calibration.json"
SUPPORTED_CALIBRATION_VERSION = 1

class SetRouteAI(Skill):

    def __init__(
        self,
        config: SkillConfig,
        settings: SettingsConfig,
        wingman: "WingmanContext",
    ):
        super().__init__(config=config, settings=settings, wingman=wingman)

        # --- Safe defaults ---
        self.search_x = 1500
        self.search_y = 200

        self.destination_x = 365
        self.destination_y = 335

        self.map_x = 1769
        self.map_y = 814

        # Set the destination engine
        self.engine = DestinationPhoneticEngine()
        
        # Save calibration file in the custom skill directory for the skill
        self.calibration_file = Path(__file__).resolve().parent / "data" / CALIBRATION_FILE
        self._desktop_lock = asyncio.Lock()
        
        #Ensure Calibration version properly set as skill variable
        self.supported_calibration_version = SUPPORTED_CALIBRATION_VERSION

    # --------------------------------------------------------------
    async def validate(self):
        errors = await super().validate()
        await self._load_mouse_calibration()
        return errors

    # --------------------------------------------------------------
    # Reset skill-owned defaults when calibration is absent or unreadable.
    async def _set_default_config(self):
        # --- Safe defaults ---
        self.search_x = 1500
        self.search_y = 200

        self.destination_x = 365
        self.destination_y = 335

        self.map_x = 1769
        self.map_y = 814

        self.engine = DestinationPhoneticEngine()

        # IMPORTANT: same path as __init__
        self.calibration_file = Path(__file__).resolve().parent / "data" / CALIBRATION_FILE

        self.supported_calibration_version = SUPPORTED_CALIBRATION_VERSION

    # --------------------------------------------------------------
    async def _load_mouse_calibration(self) -> None:
        if not self.calibration_file.exists():
            # This is the WingmanAI version of "print" so that the output displays when the user turns on debug mode
            if self.settings.debug_mode:
                await self.printr.print_async(
                    "[SetRouteAI] No mouse_calibration.json found; using defaults",
                    color=LogType.INFO,
                )
            await self._set_default_config()
            return

        try:
            with self.calibration_file.open("r", encoding="utf-8") as f:
                data = json.load(f)

            if data.get("version") != self.supported_calibration_version:
                if self.settings.debug_mode:
                    await self.printr.print_async(
                        "[SetRouteAI] Unsupported calibration version",
                        color=LogType.INFO,
                    )
                return

            starmap = data.get("starmap", {})

            if "search_bar" in starmap:
                self.search_x = int(starmap["search_bar"]["x"])
                self.search_y = int(starmap["search_bar"]["y"])

            if "destination" in starmap:
                self.destination_x = int(starmap["destination"]["x"])
                self.destination_y = int(starmap["destination"]["y"])

            if "map_center" in starmap:
                self.map_x = int(starmap["map_center"]["x"])
                self.map_y = int(starmap["map_center"]["y"])

            if self.settings.debug_mode:
                await self.printr.print_async(
                    f"""
                    [SetRouteAI] Calibration loaded: 
                    search=({self.search_x},{self.search_y}),
                    destination=({self.destination_x},{self.destination_y}),
                    map=({self.map_x},{self.map_y})
                    """,
                    color=LogType.INFO,
                )

        except Exception as exc:
            if self.settings.debug_mode:
                await self.printr.print_async(
                    f"[SetRouteAI] Failed to load calibration: {exc}. Using defaults.",
                    color=LogType.INFO,
                )
            await self._set_default_config()

    # --------------------------------------------------------------
    def get_tools(self):
        return [
            # -------- ROUTING --------
            (
                "plot_route",
                {
                    "type": "function",
                    "function": {
                        "name": "plot_route",
                        "description": "Plots a route on the map to a destination.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "destination": {"type": "string"}
                            },
                            "required": ["destination"],
                        },
                    },
                },
            ),

            # -------- CALIBRATION --------
            (
                "calibrate_mouse",
                {
                    "type": "function",
                    "function": {
                        "name": "calibrate_mouse",
                        "description": (
                            "Calibrates starmap mouse positions. "
                            "Use when the user says calibrate, calibrate mouse, "
                            "set up navigation, or align starmap controls."
                        ),
                        "parameters": {"type": "object", "properties": {}},
                    },
                },
            ),

            # -------- DESTINATIONS --------
            ("add_destination", {"type": "function", "function": {"name": "add_destination", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}}),
            ("delete_destination", {"type": "function", "function": {"name": "delete_destination", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}}),
            ("rename_destination", {"type": "function", "function": {"name": "rename_destination", "parameters": {"type": "object", "properties": {"old_name": {"type": "string"}, "new_name": {"type": "string"}}, "required": ["old_name", "new_name"]}}}),

            # -------- ALIASES --------
            ("add_alias", {"type": "function", "function": {"name": "add_alias", "parameters": {"type": "object", "properties": {"destination": {"type": "string"}, "alias": {"type": "string"}}, "required": ["destination", "alias"]}}}),
            ("delete_alias", {"type": "function", "function": {"name": "delete_alias", "parameters": {"type": "object", "properties": {"destination": {"type": "string"}, "alias": {"type": "string"}}, "required": ["destination", "alias"]}}}),
            ("list_aliases", {"type": "function", "function": {"name": "list_aliases", "parameters": {"type": "object", "properties": {"destination": {"type": "string"}}, "required": ["destination"]}}}),
        ]

    # --------------------------------------------------------------
    @staticmethod
    def _left_button_pressed() -> bool:
        # Poll Win32 instead of mouse.wait: no calibration listener/thread survives
        # cancellation, and no desktop dependency is imported by the catalog.
        return bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)

    @staticmethod
    def _mouse_position() -> tuple[int, int]:
        point = ctypes.wintypes.POINT()
        if not ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
            raise RuntimeError("Could not read mouse position")
        return int(point.x), int(point.y)

    async def _capture_mouse_position(self, prompt: str) -> tuple[int, int]:
        spoken = await self.wingman.tts.speak(prompt, interrupt=False)
        if not spoken:
            raise RuntimeError("Calibration instructions could not be spoken")

        async def wait_for_click():
            # Some TTS providers return once playback starts. Drain it through
            # the public audio facade before accepting this step's click.
            while self.wingman.audio.is_playing:
                await asyncio.sleep(0.02)
            # Ignore a button already held when instructions finish, then capture
            # the next press. Polling yields throughout and is cancellable.
            while self._left_button_pressed():
                await asyncio.sleep(0.02)
            while not self._left_button_pressed():
                await asyncio.sleep(0.02)
            position = self._mouse_position()
            while self._left_button_pressed():
                await asyncio.sleep(0.02)
            return position

        return await asyncio.wait_for(wait_for_click(), timeout=60.0)

    # --------------------------------------------------------------
    async def execute_tool(
        self, tool_name: str, parameters: dict[str, Any], benchmark: Benchmark
    ) -> tuple[str, str]:

        benchmark.start_snapshot(f"SetRouteAI: {tool_name}")
        try:
            if tool_name in {"calibrate_mouse", "plot_route"}:
                async with self._desktop_lock:
                    return await self._execute_tool(tool_name, parameters)
            return await self._execute_tool(tool_name, parameters)
        except asyncio.TimeoutError:
            if tool_name != "calibrate_mouse":
                raise
            return "Mouse calibration timed out. Previous calibration was kept; please try again.", ""
        finally:
            benchmark.finish_snapshot()

    async def _execute_tool(self, tool_name: str, parameters: dict[str, Any]) -> tuple[str, str]:
        function_response = "Error in processing the request. Please try again."
        instant_response = ""

        # -------- CALIBRATION --------
        if tool_name == "calibrate_mouse":
            # Get language selection from custom_properties
            lang = "en"
            if hasattr(self.config, "custom_properties") and self.config.custom_properties:
                for prop in self.config.custom_properties:
                    if getattr(prop, "id", None) == "language":
                        lang = getattr(prop, "value", "en")
                        break

            # Translations for calibration instructions
            translations = {
                "en": [
                    "Calibration Beginning: Step 1 of 3: Press F2, then zoom out with the mouse and left click on the Search bar",
                    "Step 2 of 3: In the search bar type a destination in the same system as you and click on the Destination result",
                    "Step 3 of 3: Click in the center of the screen above your player or ship icon"
                ],
                "es": [
                    "Inicio de calibración: Paso 1 de 3: Presiona F2, luego aleja el zoom con el ratón y haz clic izquierdo en la barra de búsqueda",
                    "Paso 2 de 3: En la barra de búsqueda escribe un destino en el mismo sistema que tú y haz clic en el resultado del destino",
                    "Paso 3 de 3: Haz clic en el centro de la pantalla sobre el icono de tu jugador o nave"
                ],
                "zh": [
                    "开始校准：第 1 步（共 3 步）：按 F2，然后用鼠标缩小并左键单击搜索栏",
                    "第 2 步（共 3 步）：在搜索栏中输入与您在同一系统中的目的地，然后单击目的地结果",
                    "第 3 步（共 3 步）：点击屏幕中央您的玩家或飞船图标上方"
                ],
                "ja": [
                    "キャリブレーション開始：ステップ 1/3：F2 キーを押し、マウスでズームアウトしてから検索バーを左クリックしてください",
                    "ステップ 2/3：検索バーにあなたと同じシステム内の目的地を入力し、目的地の結果をクリックしてください",
                    "ステップ 3/3：画面中央のプレイヤーまたは船のアイコンの上をクリックしてください"
                ],
                "de": [
                    "Kalibrierung beginnt: Schritt 1 von 3: Drücken Sie F2, zoomen Sie dann mit der Maus heraus und klicken Sie mit der linken Maustaste auf die Suchleiste",
                    "Schritt 2 von 3: Geben Sie in der Suchleiste ein Ziel im selben System wie Sie ein und klicken Sie auf das Zielergebnis",
                    "Schritt 3 von 3: Klicken Sie in die Mitte des Bildschirms über Ihrem Spieler- oder Schiffssymbol"
                ]
            }

            # Select the appropriate instructions set
            steps = translations.get(lang, translations["en"])

            sx, sy = await self._capture_mouse_position(steps[0])
            dx, dy = await self._capture_mouse_position(steps[1])
            mx, my = await self._capture_mouse_position(steps[2])

            data = {
                "version": self.supported_calibration_version,
                "starmap": {
                    "search_bar": {"x": sx, "y": sy},
                    "destination": {"x": dx, "y": dy},
                    "map_center": {"x": mx, "y": my},
                },
            }
            # Create the directory if it doesn't exist
            self.calibration_file.parent.mkdir(parents=True, exist_ok=True)
            with self.calibration_file.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            self.search_x, self.search_y = sx, sy
            self.destination_x, self.destination_y = dx, dy
            self.map_x, self.map_y = mx, my

            function_response = "Mouse calibration complete."

        # -------- ROUTE --------
        if tool_name == "plot_route":
            original = (parameters.get("destination") or "").strip()
            if not original:
                return "No destination specified.", ""
            if self.settings.debug_mode:
                await self.printr.print_async(
                    f"RouteAI: Attempting to find match destination for input: {original}...",
                    color=LogType.INFO,
                )
            normalized, alternatives = self.engine.find_destination(original)
            
            # If multiple matches found, use LLM to decide
            if normalized is None and len(alternatives) > 1:
                if self.settings.debug_mode:
                    await self.printr.print_async(
                        f"RouteAI: Found multiple matches for '{original}', asking LLM to choose from: {alternatives}...",
                        color=LogType.INFO,
                    )
                normalized = await self._fuzzy_llm_match(original, alternatives)
            
            # If still did not receive destination, then let user know 
            if normalized is None:
                if self.settings.debug_mode:
                    await self.printr.print_async(
                        f"RouteAI: Could not find match destination for input: {original}.",
                        color=LogType.INFO,
                    )
                function_response = f"Could not locate match or potential match for destination - {original} in system navigation database. Plotting route failed."
            # Otherwise, if destination found, apply learning and plot route
            else:
                if self.settings.debug_mode:
                    await self.printr.print_async(
                        f"RouteAI: Found matching destination for input: {original}, routing to {normalized}.",
                        color=LogType.INFO,
                    )
                await self._register_learning(original, normalized)
                function_response = await self._plot_route(normalized)

        # -------- DESTINATION / ALIAS MGMT --------

        # ----------------- ADD DESTINATION ------------------
        if tool_name == "add_destination":
            name = (parameters.get("name") or "").strip()
            if not name:
                function_response = "No destination name provided."
                return function_response, instant_response

            key = self.engine.normalize(name)
            if key in self.engine.destinations:
                function_response = f'The destination "{name}" already exists.'
                return function_response, instant_response

            self.engine.destinations[key] = {"aliases": []}
            self.engine._save_json(self.engine.destinations_file, self.engine.destinations)
            function_response = f'I have added "{name}" as a known destination.'

        # ----------------- DELETE DESTINATION ------------------
        if tool_name == "delete_destination":
            name = (parameters.get("name") or "").strip()
            if not name:
                function_response = "No destination specified to delete."
                return function_response, instant_response

            key = self.engine.normalize(name)
            if key not in self.engine.destinations:
                function_response = f'The destination "{name}" does not exist.'
                return function_response, instant_response

            self.engine.destinations.pop(key)
            self.engine._save_json(self.engine.destinations_file, self.engine.destinations)
            function_response = f'The destination "{name}" has been deleted.'

        # ----------------- RENAME DESTINATION ----------------
        if tool_name == "rename_destination":
            old = (parameters.get("old_name") or "").strip()
            new = (parameters.get("new_name") or "").strip()

            if not old or not new:
                function_response = "You must provide both the old and the new name."
                return function_response, instant_response

            old_key = self.engine.normalize(old)
            new_key = self.engine.normalize(new)

            if old_key not in self.engine.destinations:
                function_response = f'The destination "{old}" does not exist.'
                return function_response, instant_response

            if new_key in self.engine.destinations:
                function_response = f'A destination with the name "{new}" already exists.'
                return function_response, instant_response

            self.engine.destinations[new_key] = self.engine.destinations.pop(old_key)
            self.engine._save_json(self.engine.destinations_file, self.engine.destinations)
            function_response = f'The destination has been renamed from "{old}" to "{new}".'

        # ----------------- ADD ALIAS ---------------------
        if tool_name == "add_alias":
            dest = (parameters.get("destination") or "").strip()
            alias = (parameters.get("alias") or "").strip()

            if not dest or not alias:
                function_response = "You must provide both a destination and an alias."
                return function_response, instant_response

            result = self.engine.add_alias(dest, alias)

            if result == "destination_not_found":
                function_response = f'The destination "{dest}" does not exist.'
                return function_response, instant_response
            if result == "alias_exists":
                function_response = f'The alias "{alias}" already exists for the destination "{dest}".'
                return function_response, instant_response

            function_response = f'I have added the alias "{alias}" to the destination "{dest}".'

        # ----------------- DELETE ALIAS -------------------
        if tool_name == "delete_alias":
            dest = (parameters.get("destination") or "").strip()
            alias = (parameters.get("alias") or "").strip()

            if not dest or not alias:
                function_response = "You must provide both a destination and the alias to delete."
                return function_response, instant_response

            result = self.engine.remove_alias(dest, alias)

            if result == "destination_not_found":
                function_response = f'The destination "{dest}" does not exist.'
                return function_response, instant_response
                
            if result == "alias_not_found":
                function_response = f'The alias "{alias}" is not associated with the destination "{dest}".'
                return function_response, instant_response

            function_response = f'I have deleted the alias "{alias}" from the destination "{dest}".'

        # ----------------- LIST ALIASES FOR A DESTINATION -----
        if tool_name == "list_aliases":
            dest = (parameters.get("destination") or "").strip()
            if not dest:
                function_response = "You must provide the destination for which you want to see the aliases."
                return function_response, instant_response

            aliases = self.engine.get_aliases(dest)
            if aliases is None:
                function_response = f'The destination "{dest}" does not exist.'
                return function_response, instant_response

            if not aliases:
                function_response = f'The destination "{dest}" has no defined aliases.'
                return function_response, instant_response

            lista = "\n".join(f"- {a}" for a in aliases)
            function_response = f'Aliases for "{dest}":\n{lista}'
        
        return function_response, instant_response
    
    # --------------------------------------------------------------
    async def _fuzzy_llm_match(self, phrase: str, candidates: List[str]):
        if not candidates:
            return None
            
        system_prompt = f"""
            #PRIME OBJECTIVE
            You are a specialist with expertise in determining matches between the phrase provided and real destinations in the video game Star Citizen. 
            When provided with the phrase the user said (which might have been mispronounced or misunderstood) AND a list of top fuzzy matches from the database, return the most likely real Star Citizen destination the user intended from that list.
            Your response is directly input into the user's starmap and used for quantum leaps so it is important your response ONLY includes the destination and no other words.
            
            ##BACKGROUND INFORMATION:
            A list of potential Star Citizen destinations that fuzzy matched the user's phrase is: {candidates}.
            You must choose the best match from this provided list.
            
            ##EXAMPLES:
            Here are three examples of your successful work in this area.
            *Example 1*
            Input phrase: port trestler
            Candidates: ['Port Tressler', 'Port Olisar', 'Tressler Station']
            You responded: Port Tressler
            Feedback: Correct because although the user misspoke, Port Tressler is the closest intentional match in the candidates list.
            *Example 2*:
            Input phrase: Nick's gateway
            Candidates: ['Nyx Gateway', 'Nix Station', 'Gateway 1']
            You responded: Nyx Gateway
            Feedback: Correct choice from the candidates list.
            *Example 3*:
            Input phrase: Bob's burgers
            Candidates: ['Port Olisar', 'Grim HEX']
            You responded: Unknown
            Feedback: Correct because none of the candidates are a reasonable match for the input.
        """
        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Input phrase: {phrase}. Choose the best match from the following candidates: {candidates}. Return just the proper destination name. If there is no possible match, then simply respond: Unknown"},
                ],
            },
        ]
        answer = await self.wingman.ai.generate(messages=messages)
        # A side-call returns text, not a completion object. Never type an LLM's
        # arbitrary output into the game; resolve back to a supplied candidate.
        answer = answer.strip().casefold()
        return next((candidate for candidate in candidates
                     if candidate.strip().casefold() == answer), None)

    # --------------------------------------------------------------
    async def _register_learning(self, phrase: str, normalized: str):
        if phrase and normalized and phrase.lower() != normalized.lower():
            self.engine.learn(phrase.lower(), normalized.lower())

    # --------------------------------------------------------------
    @staticmethod
    def _set_clipboard(text: str):
        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        # --- CRITICAL: Declare proper 64-bit return types ---
        kernel32.GlobalAlloc.restype  = ctypes.c_void_p
        kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
        kernel32.GlobalLock.restype   = ctypes.c_void_p
        kernel32.GlobalLock.argtypes  = [ctypes.c_void_p]
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalFree.restype   = ctypes.c_void_p
        kernel32.GlobalFree.argtypes  = [ctypes.c_void_p]
        user32.OpenClipboard.argtypes = [ctypes.c_void_p]
        user32.SetClipboardData.restype  = ctypes.c_void_p
        user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
        text_bytes = (text + "\0").encode("utf-16-le")
        size = len(text_bytes)
        h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, size)
        if not h_mem:
            raise RuntimeError("GlobalAlloc failed")
        p_mem = kernel32.GlobalLock(h_mem)
        if not p_mem:
            kernel32.GlobalFree(h_mem)
            raise RuntimeError("GlobalLock failed")
        ctypes.memmove(p_mem, text_bytes, size)
        kernel32.GlobalUnlock(h_mem)
        if not user32.OpenClipboard(None):
            kernel32.GlobalFree(h_mem)
            raise RuntimeError("OpenClipboard failed")
        try:
            if not user32.EmptyClipboard():
                raise RuntimeError("EmptyClipboard failed")
            if not user32.SetClipboardData(CF_UNICODETEXT, h_mem):
                raise RuntimeError("SetClipboardData failed")
            h_mem = None  # Windows now owns the allocation.
        finally:
            user32.CloseClipboard()
            if h_mem:
                kernel32.GlobalFree(h_mem)

    # --------------------------------------------------------------
    async def _plot_route(self, destination: str) -> str:
        # Desktop packages can initialize OS hooks: import only on actual routing.
        import mouse.mouse as mouse
        import keyboard.keyboard as keyboard

        PAUSE = 3.0
        HOLD = 1.4

        # --- Open Starmap ---
        keyboard.press("f2")
        try:
            await asyncio.sleep(HOLD)
        finally:
            keyboard.release("f2")
        await asyncio.sleep(3.5)

        # --- Move mouse into map area ---
        mouse.move(self.map_x, self.map_y)
        mouse.click()
        await asyncio.sleep(1.3)

        # --- Scroll Out ---
        mouse.wheel(-60)
        await asyncio.sleep(2.1)

        # --- Click Search ---
        mouse.move(self.search_x, self.search_y)
        mouse.click()
        await asyncio.sleep(1.5)

        # --- Paste destination via clipboard ---
        self._set_clipboard(destination)
        await asyncio.sleep(0.3)
        keyboard.press("ctrl")
        keyboard.press("v")
        keyboard.release("v")
        keyboard.release("ctrl")
        await asyncio.sleep(1.0)

        # --- Click Destination result ---
        mouse.move(self.destination_x, self.destination_y)
        mouse.click()
        await asyncio.sleep(0.5)

        # --- Move mouse into map area ---
        mouse.move(self.map_x, self.map_y)
        mouse.click()
        await asyncio.sleep(1.3)

        keyboard.press("r")
        keyboard.release("r")
        keyboard.press("r")
        keyboard.release("r")
        keyboard.press("r")
        keyboard.release("r")
        keyboard.press("r")
        keyboard.release("r")
        await asyncio.sleep(PAUSE)

        keyboard.press("f2")
        try:
            await asyncio.sleep(HOLD)
        finally:
            keyboard.release("f2")

        if self.settings.debug_mode:
            await self.printr.print_async(
                f"RouteAI: Sent route macro for: {destination}. Used map position: {self.map_x}, {self.map_y}; search position: {self.search_x}, {self.search_y}; destination position: {self.destination_x}, {self.destination_y}.",
                color=LogType.INFO,
            )
        return f"Route macro sent for {destination}. The in-game route was not verified. Use the proper name: {destination} when responding to the user."
