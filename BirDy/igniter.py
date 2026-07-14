import argparse
import asyncio
import threading
import json
import sys
import traceback
import logging
import time
from pathlib import Path
from datetime import datetime

import pyaudio
import psutil
import pyautogui
from google import genai
from google.genai import types
from typing import Optional

# --- CONFIGURATION & LOGGING ---
logging.basicConfig(
    level=logging.WARNING, # Suppress noise
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('jarvis_neural.log', mode='w', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ],
    force=True
)
logger = logging.getLogger("JARVIS")
logger.setLevel(logging.INFO) # Only JARVIS logs at info level

# Core Constants
LIVE_MODEL          = "models/gemini-2.5-flash-native-audio-preview-12-2025"
SEND_SAMPLE_RATE    = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE          = 1024
PA_FORMAT           = pyaudio.paInt16
CHANNELS            = 1

# Global Living Context
SENSORY_HUB = {
    "visual_context": "No visual data yet.",
    "system_health": "Optimal",
    "last_alert": None
}

# Project-specific imports
from monitor import BirDyUI, API_FILE
from neural_store.main import load_memory, update_memory, format_memory_for_prompt

# Ability Core modules
from ability_core.open_app          import open_app
from ability_core.weather_report    import weather_action
from ability_core.send_message      import send_message
from ability_core.reminder          import reminder
from ability_core.computer_settings import computer_settings
from ability_core.screen_processor  import screen_process
from ability_core.youtube_video     import youtube_video
from ability_core.desktop           import desktop_control
from ability_core.browser_control   import browser_control
from ability_core.code_helper       import code_helper
from ability_core.dev_agent         import dev_agent
from ability_core.web_search        import web_search as web_search_action
from ability_core.computer_control  import computer_control
from ability_core.file_controller   import file_controller
from ability_core.cmd_control       import cmd_control

# --- SYSTEM PATHS ---
def get_base_dir():
    if getattr(sys, "frozen", False): return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR        = get_base_dir()
API_CONFIG_PATH = BASE_DIR / "Brightos" / "security_vault" / "access.json"
if not API_CONFIG_PATH.exists():
    API_CONFIG_PATH = Path(__file__).resolve().parent / "security_vault" / "access.json"

PROMPT_PATH = Path(__file__).resolve().parent / "system_laws" / "rules.txt"

pya = pyaudio.PyAudio()

def _get_api_key() -> str:
    try:
        with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)["gemini_api_key"]
    except: return ""

def _load_system_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except:
        return (
            "You are BİRDY, the autonomous artificial intelligence created by Veynor. "
            "Your style is fast, female, and JARVIS-like. Respond in Turkish unless asked otherwise."
        )


def _get_full_prompt() -> str:
    mem_str = format_memory_for_prompt(load_memory())
    sys_p = _load_system_prompt()
    now      = datetime.now()
    time_str = now.strftime("%A, %B %d, %Y — %I:%M %p")
    
    # Inject Living Context
    sensory_p = (
        f"\n[SENSORY CONTEXT — WHAT YOU SEE & FEEL]\n"
        f"Visual Input: {SENSORY_HUB['visual_context']}\n"
        f"System Status: {SENSORY_HUB['system_health']}\n"
        f"Latest Alert: {SENSORY_HUB.get('last_alert', 'None')}\n"
    )

    time_ctx = (
        f"[CURRENT DATE & TIME]\n"
        f"Right now it is: {time_str}\n"
        f"Use this for accurate timing.\n\n"
    )
    return time_ctx + sensory_p + (mem_str + "\n\n" + sys_p if mem_str else sys_p)

# FULL MODULE DECLARATIONS
MODULE_DECLARATIONS = [
    {"name": "open_app", "description": "Opens system applications.", "parameters": {"type": "OBJECT", "properties": {"app_name": {"type": "STRING"}}, "required": ["app_name"]}},
    {"name": "web_search", "description": "Global information retrieval.", "parameters": {"type": "OBJECT", "properties": {"query": {"type": "STRING"}}, "required": ["query"]}},
    {"name": "weather_report", "description": "Environmental synchronization.", "parameters": {"type": "OBJECT", "properties": {"city": {"type": "STRING"}}, "required": ["city"]}},
    {"name": "send_message", "description": "Sends messages via WhatsApp, Telegram, or Instagram.", "parameters": {"type": "OBJECT", "properties": {"receiver": {"type": "STRING"}, "message_text": {"type": "STRING"}, "platform": {"type": "STRING", "enum": ["whatsapp", "telegram", "instagram"]}}, "required": ["receiver", "message_text"]}},
    {"name": "reminder", "description": "Sets a reminder for a specific date and time.", "parameters": {"type": "OBJECT", "properties": {"date": {"type": "STRING", "description": "YYYY-MM-DD"}, "time": {"type": "STRING", "description": "HH:MM"}, "message": {"type": "STRING"}}, "required": ["date", "time", "message"]}},
    {"name": "computer_settings", "description": "Controls system settings like volume, brightness, and window management.", "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING"}, "description": {"type": "STRING"}, "value": {"type": "STRING"}}, "required": []}},
    {"name": "screen_process", "description": "Analyzes screen content or takes a screenshot.", "parameters": {"type": "OBJECT", "properties": {"text": {"type": "STRING"}}, "required": ["text"]}},
    {"name": "youtube_video", "description": "Plays or summarizes YouTube videos.", "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING", "enum": ["play", "summarize", "get_info", "trending"]}, "query": {"type": "STRING"}, "url": {"type": "STRING"}}, "required": []}},
    {"name": "desktop_control", "description": "Manages desktop wallpaper, files, and organization.", "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING"}, "task": {"type": "STRING"}, "path": {"type": "STRING"}}, "required": []}},
    {"name": "browser_control", "description": "Controls the web browser (navigation, clicking, typing).", "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING"}, "url": {"type": "STRING"}, "query": {"type": "STRING"}, "text": {"type": "STRING"}}, "required": []}},
    {"name": "code_helper", "description": "Assists with coding tasks (write, edit, explain, run, optimize).", "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING"}, "description": {"type": "STRING"}, "language": {"type": "STRING"}}, "required": ["description"]}},
    {"name": "dev_agent", "description": "Builds full projects from a description.", "parameters": {"type": "OBJECT", "properties": {"description": {"type": "STRING"}, "language": {"type": "STRING"}, "project_name": {"type": "STRING"}}, "required": ["description"]}},
    {"name": "computer_control", "description": "Atomic mouse and keyboard control.", "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING"}, "text": {"type": "STRING"}, "x": {"type": "INTEGER"}, "y": {"type": "INTEGER"}}, "required": []}},
    {"name": "file_controller", "description": "Manages local files and folders (list, create, delete, move, rename).", "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING"}, "path": {"type": "STRING"}, "name": {"type": "STRING"}}, "required": []}},
    {"name": "cmd_control", "description": "Executes shell commands directly.", "parameters": {"type": "OBJECT", "properties": {"command": {"type": "STRING"}}, "required": ["command"]}},
    {"name": "vision_control", "description": "Toggles visual analysis mode.", "parameters": {"type": "OBJECT", "properties": {"mode": {"type": "STRING", "enum": ["on", "off"]}}, "required": ["mode"]}}
]

class VisionWatcher:
    """The 'Eyes' of Jarvis — Periodically scans screen/camera."""
    def __init__(self, ui):
        self.ui = ui
        self.active = True

    def _get_frame(self):
        try:
            scr = pyautogui.screenshot()
            scr = scr.resize((600, 360))
            return "Visible: Windows Desktop. User active."
        except: return "Visual feed interrupted."

    def start(self):
        def loop():
            while self.active:
                SENSORY_HUB["visual_context"] = self._get_frame()
                time.sleep(120) # Update context every 2 min
        threading.Thread(target=loop, daemon=True).start()

class ProactiveHeartbeat:
    """The 'Nervous System' — Detects system anomalies."""
    def __init__(self, ui):
        self.ui = ui

    def start(self):
        def loop():
            while True:
                cpu = psutil.cpu_percent()
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage(str(Path.home()))

                if cpu > 85:
                    status = f"High CPU load ({cpu}%)"
                    self.ui.write_log(f"ALERT: CPU spike detected ({cpu}%)")
                elif memory.percent > 85:
                    status = f"Memory pressure ({memory.percent}%)"
                    self.ui.write_log(f"ALERT: Memory usage high ({memory.percent}%)")
                elif disk.percent > 90:
                    status = f"Low disk space ({100 - disk.percent:.0f}% free)"
                    self.ui.write_log(f"ALERT: Disk space critical ({100 - disk.percent:.0f}% free)")
                else:
                    status = "Stable"

                SENSORY_HUB["system_health"] = status
                self.ui.update_sensory(vision=self.ui.visual_status, health=status)

                if status != "Stable":
                    self.ui.show_proactive_alert(status)

                time.sleep(15)
        threading.Thread(target=loop, daemon=True).start()


class SystemEventWatcher:
    """Monitors desktop, downloads and common application folders."""
    def __init__(self, ui, interval: int = 8):
        self.ui = ui
        self.interval = interval
        self.active = True
        self.directories = {
            "Desktop": Path.home() / "Desktop",
            "Downloads": Path.home() / "Downloads"
        }
        self.app_folders = self._resolve_app_directories()
        self._snapshots = {
            **self._snapshot_dirs(self.directories),
            **self._snapshot_dirs(self.app_folders)
        }

    def _resolve_app_directories(self) -> dict[str, Path]:
        if sys.platform == "win32":
            return {
                "Program Files": Path("C:/Program Files"),
                "Program Files (x86)": Path("C:/Program Files (x86)")
            }
        if sys.platform == "darwin":
            return {
                "Applications": Path("/Applications")
            }
        return {
            "Applications": Path("/usr/share/applications")
        }

    def _snapshot_folder(self, folder: Path) -> dict[str, float]:
        if not folder.exists() or not folder.is_dir():
            return {}
        snapshot = {}
        try:
            for child in folder.iterdir():
                snapshot[str(child.resolve())] = child.stat().st_mtime
        except PermissionError:
            pass
        except Exception:
            pass
        return snapshot

    def _snapshot_dirs(self, paths: dict[str, Path]) -> dict[str, dict[str, float]]:
        return {name: self._snapshot_folder(path) for name, path in paths.items()}

    def _should_watch(self) -> bool:
        # Keep watchers light to avoid slowing down core response.
        return False

    def _report_event(self, event: str, file_path: Path, category: str) -> None:
        display_name = file_path.name
        if category in ("Program Files", "Program Files (x86)", "Applications"):
            message = f"New app event: {event} {display_name}"
        else:
            message = f"File event: {event} {display_name}"

        self.ui.write_log(f"SYS: {message}")
        self.ui.show_proactive_alert(message)
        update_memory({"notes": {"recent_system_event": {"value": message}}})
        SENSORY_HUB["last_alert"] = message

    def start(self):
        if not self._should_watch():
            return
        def loop():
            while self.active:
                for category, path in {**self.directories, **self.app_folders}.items():
                    before = self._snapshots.get(category, {})
                    current = self._snapshot_folder(path)
                    added = [Path(p) for p in current if p not in before]
                    removed = [Path(p) for p in before if p not in current]

                    for item in added:
                        self._report_event("added to", item, category)
                    for item in removed:
                        self._report_event("removed from", item, category)

                    self._snapshots[category] = current
                time.sleep(self.interval)
        threading.Thread(target=loop, daemon=True).start()


def _call_ability(fn, parameters: dict, player=None, speak=None):
    kwargs = {"parameters": parameters}
    if player is not None:
        kwargs["player"] = player
    if speak is not None:
        kwargs["speak"] = speak

    try:
        return fn(**kwargs)
    except TypeError:
        try:
            return fn(parameters=parameters, player=player)
        except TypeError:
            return fn(parameters=parameters)


class BirDyLive:
    def __init__(self, ui: BirDyUI):
        self.ui             = ui
        self.session        = None
        self.audio_in_queue = asyncio.Queue(maxsize=40)
        self.out_queue      = asyncio.Queue(maxsize=40)
        self._loop          = None
        self.vision_watcher = VisionWatcher(self.ui)

    def _build_config(self) -> types.LiveConnectConfig:
        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction=_get_full_prompt(),
            tools=[{"function_declarations": MODULE_DECLARATIONS}],
            session_resumption=types.SessionResumptionConfig(),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Charon")
                )
            ),
        )

    def speak_text(self, text: str):
        if text:
            self.ui.write_log(f"Jarvis: {text}")
        return text

    async def _execute_tool(self, fc) -> types.FunctionResponse:
        name = fc.name; args = dict(fc.args or {})
        loop = asyncio.get_event_loop(); result = "Acknowledged."
        
        # Tool Mapping System
        TOOL_MAP = {
            "open_app":          lambda: _call_ability(open_app, parameters=args, player=self.ui, speak=self.speak_text),
            "web_search":        lambda: _call_ability(web_search_action, parameters=args, player=self.ui, speak=self.speak_text),
            "weather_report":    lambda: _call_ability(weather_action, parameters=args, player=self.ui, speak=self.speak_text),
            "send_message":      lambda: _call_ability(send_message, parameters=args, player=self.ui, speak=self.speak_text),
            "reminder":          lambda: _call_ability(reminder, parameters=args, player=self.ui, speak=self.speak_text),
            "computer_settings": lambda: _call_ability(computer_settings, parameters=args, player=self.ui, speak=self.speak_text),
            "youtube_video":     lambda: _call_ability(youtube_video, parameters=args, player=self.ui, speak=self.speak_text),
            "desktop_control":   lambda: _call_ability(desktop_control, parameters=args, player=self.ui, speak=self.speak_text),
            "browser_control":   lambda: _call_ability(browser_control, parameters=args, player=self.ui, speak=self.speak_text),
            "code_helper":       lambda: _call_ability(code_helper, parameters=args, player=self.ui, speak=self.speak_text),
            "dev_agent":         lambda: _call_ability(dev_agent, parameters=args, player=self.ui, speak=self.speak_text),
            "computer_control":  lambda: _call_ability(computer_control, parameters=args, player=self.ui, speak=self.speak_text),
            "file_controller":   lambda: _call_ability(file_controller, parameters=args, player=self.ui, speak=self.speak_text),
            "cmd_control":       lambda: _call_ability(cmd_control, parameters=args, player=self.ui, speak=self.speak_text)
        }

        try:
            if name in TOOL_MAP:
                r = await loop.run_in_executor(None, TOOL_MAP[name])
                result = r or f"Processed {name}."
            elif name == "screen_process":
                threading.Thread(target=screen_process, kwargs={"parameters": args, "player": self.ui}, daemon=True).start()
                result = "Analyzing screen context..."
            elif name == "vision_control":
                mode = args.get("mode", "off")
                self.vision_watcher.active = (mode == "on")
                result = f"Visual tele-sync {mode}, efendim."
            else:
                result = f"Command {name} executed."
        except Exception as e:
            result = f"Neural Error: {e}"
        
        return types.FunctionResponse(id=fc.id, name=name, response={"result": result})

    async def _send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            if self.session and self.out_queue:
                try: await self.session.send_realtime_input(media=msg)
                except: pass

    async def _listen_audio(self):
        logger.info("🎤 Mic sensing active")
        stream = await asyncio.to_thread(
            pya.open, format=PA_FORMAT, channels=CHANNELS, rate=SEND_SAMPLE_RATE, input=True, frames_per_buffer=CHUNK_SIZE
        )
        try:
            while True:
                data = await asyncio.to_thread(stream.read, CHUNK_SIZE, exception_on_overflow=False)
                # Only send audio if Jarvis is NOT speaking to avoid echo loop
                if not self.ui.speaking and not self.out_queue.full():
                    await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})
        except Exception as e:
            logger.error(f"[JARVIS] 🎤 Mic fatal: {e}")
            raise
        finally: stream.close()

    async def _receive_audio(self):
        logger.info("[JARVIS] 👂 Downlink active")
        try:
            while True:
                if not self.session: break
                turn = self.session.receive()
                async for response in turn:
                    if not self.session: break
                    if response.data and not self.audio_in_queue.full():
                        self.audio_in_queue.put_nowait(response.data)

                    if response.server_content:
                        sc = response.server_content
                        # Multi-attribute mapping
                        it = getattr(sc, 'input_transcription', None) or getattr(sc, 'input_audio_transcription', None)
                        if it and it.text:
                            logger.info(f"USER: {it.text}")
                            self.ui.write_log(f"You: {it.text}")
                        
                        ot = getattr(sc, 'output_transcription', None) or getattr(sc, 'output_audio_transcription', None)
                        if ot and ot.text:
                            logger.info(f"AI: {ot.text}")
                            self.ui.write_log(f"Jarvis: {ot.text}")

                        if sc.interrupted:
                            while not self.audio_in_queue.empty():
                                try: self.audio_in_queue.get_nowait()
                                except asyncio.QueueEmpty: break
                            self.ui.stop_speaking(); self.ui.write_log("SYS: Interrupted.")
                        
                        if sc.turn_complete:
                            pass

                    if response.tool_call:
                        fn_responses = []
                        for fc in response.tool_call.function_calls:
                            logger.info(f"[JARVIS] 📞 Tool: {fc.name}")
                            fr = await self._execute_tool(fc)
                            fn_responses.append(fr)
                        await self.session.send_tool_response(function_responses=fn_responses)
        except Exception as e:
            logger.error(f"[JARVIS] 👂 Downlink fatal: {e}")
            traceback.print_exc()

    async def _play_audio(self):
        logger.info("🔊 Neural speaker active")
        stream = await asyncio.to_thread(
            pya.open, format=PA_FORMAT, channels=CHANNELS, rate=RECEIVE_SAMPLE_RATE, output=True, frames_per_buffer=1024
        )
        try:
            while True:
                if self.audio_in_queue is None:
                    await asyncio.sleep(0.1)
                    continue
                chunk = await self.audio_in_queue.get()
                self.ui.start_speaking() # Signal UI and mute Mic
                await asyncio.to_thread(stream.write, chunk)
                if self.audio_in_queue.empty():
                    self.ui.stop_speaking() # Unmute Mic and signal UI
        except Exception as e:
            logger.error(f"[JARVIS] 🔊 Speaker fatal: {e}")
            raise
        finally: stream.close()

    async def run_session(self):
        logger.info("[JARVIS] 🚀 Neural Hub Booting...")
        
        # Wait for API Authorization if needed
        while not self.ui._api_key_ready:
            logger.info("[JARVIS] ⚠ Waiting for API Master Key authorization...")
            await asyncio.sleep(2)

        self.vision_watcher.start()
        ProactiveHeartbeat(self.ui).start()
        SystemEventWatcher(self.ui).start()

        while True:
            try:
                # Initialize queues within the session loop to ensure they attach to the correct event loop
                self.audio_in_queue = asyncio.Queue()
                self.out_queue      = asyncio.Queue(maxsize=100)
                client = genai.Client(api_key=_get_api_key(), http_options={"api_version": "v1alpha"})
                
                async with (
                    client.aio.live.connect(model=LIVE_MODEL, config=self._build_config()) as session,
                    asyncio.TaskGroup() as tg
                ):
                    self.session = session; self._loop = asyncio.get_event_loop()
                    self.ui.write_log("SYS: Neural Engine ONLINE.")
                    logger.info("[JARVIS] ✨ Link Established.")
                    
                    # Proactive Activation Greeting
                    try:
                        await session.send_realtime_input(text="Çevrim içi ve emrinizdeyim efendim.")
                    except: pass
                    
                    tg.create_task(self._send_realtime())
                    tg.create_task(self._listen_audio())
                    tg.create_task(self._receive_audio())
                    tg.create_task(self._play_audio())
            except Exception as e:
                logger.error(f"[JARVIS] ❌ Hub Crash: {e}"); await asyncio.sleep(2)

    def start(self):
        threading.Thread(target=lambda: asyncio.run(self.run_session()), daemon=True).start()
        if hasattr(self.ui, "root"):
            self.ui.root.mainloop()
        else:
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass


class HeadlessUI:
    def __init__(self):
        self.speaking = False
        self.status_text = "HYPER-STREAM READY"
        self.visual_status = "AWARE"
        self.health_status = "STABLE"
        self.alert_text = ""
        self._api_key_ready = False

        if API_FILE.exists():
            try:
                with open(API_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("gemini_api_key"):
                        self._api_key_ready = True
            except Exception:
                pass

        if not self._api_key_ready:
            raise RuntimeError("Headless mode requires a valid gemini_api_key in security_vault/access.json.")

    def write_log(self, text: str):
        print(text)

    def update_sensory(self, vision="AWARE", health="STABLE"):
        self.visual_status = vision
        self.health_status = health

    def show_proactive_alert(self, text: str):
        self.alert_text = text
        self.write_log(f"ALERT: {text}")

    def start_speaking(self):
        self.speaking = True
        self.status_text = "HYPER-STREAM DATA INJECT"

    def stop_speaking(self):
        self.speaking = False
        self.status_text = "READY FOR SIGNAL"

    def request_new_key(self, message="INVALID KEY DETECTED"):
        self.write_log(f"SYS: {message}")

    def wait_for_api_key(self):
        if not self._api_key_ready:
            raise RuntimeError("API key missing for headless execution.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Launch BİRDY Neural Link")
    parser.add_argument("--headless", action="store_true", help="Run without GUI")
    args = parser.parse_args()

    if args.headless:
        app_ui = HeadlessUI()
        core = BirDyLive(app_ui)
        core.start()
    else:
        app_ui = BirDyUI()
        core = BirDyLive(app_ui)
        core.start()
