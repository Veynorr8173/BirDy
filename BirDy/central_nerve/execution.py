import json
import re
import sys
import threading
import subprocess
import tempfile
import os
from pathlib import Path
from typing import Callable

from central_nerve.planner import generate_strategy, refactor_strategy
from central_nerve.analyst import analyze_error, generate_fix, ErrorDecision

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


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR        = get_base_dir()
API_CONFIG_PATH = BASE_DIR / "security_vault" / "access.json"


def _get_api_key() -> str:
    with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]

def _execute_dynamic_module(description: str, speak: Callable | None = None) -> str:
    import google.generativeai as genai

    if speak:
        speak("Synthesizing custom logic, efendim.")

    genai.configure(api_key=_get_api_key())
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=(
            "You are a BrightOS Advanced Developer. "
            "Write clean, high-integrity Python logic to fulfill the objective. "
            "Return raw code only."
        )
    )

    try:
        response = model.generate_content(f"Logic for: {description}")
        code = response.text.strip()
        code = re.sub(r"```(?:python)?", "", code).strip().rstrip("`").strip()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            tmp_path = f.name

        print(f"[BrightExecutor] 🧱 Deploying logic: {tmp_path}")
        result = subprocess.run([sys.executable, tmp_path], capture_output=True, text=True, timeout=120, cwd=str(Path.home()))
        try: os.unlink(tmp_path)
        except: pass

        if result.returncode == 0: return result.stdout.strip() or "Operation complete."
        else: raise RuntimeError(f"Logic Error: {result.stderr[:200]}")

    except Exception as e:
        raise RuntimeError(f"Deployment failure: {e}")


def _dispatch_tool(step: dict, speak: Callable | None = None) -> str:
    tool = step.get("tool", "").strip()
    parameters = step.get("parameters", {}) or {}

    dispatch_map = {
        "open_app":          lambda: open_app(parameters=parameters),
        "web_search":        lambda: web_search_action(parameters=parameters),
        "weather_report":    lambda: weather_action(parameters=parameters),
        "send_message":      lambda: send_message(parameters=parameters),
        "reminder":          lambda: reminder(parameters=parameters),
        "computer_settings": lambda: computer_settings(parameters=parameters),
        "youtube_video":     lambda: youtube_video(parameters=parameters),
        "desktop_control":   lambda: desktop_control(parameters=parameters),
        "browser_control":   lambda: browser_control(parameters=parameters),
        "code_helper":       lambda: code_helper(parameters=parameters),
        "dev_agent":         lambda: dev_agent(parameters=parameters),
        "computer_control":  lambda: computer_control(parameters=parameters),
        "file_controller":   lambda: file_controller(parameters=parameters),
        "cmd_control":       lambda: cmd_control(parameters=parameters),
    }

    if tool == "screen_process":
        return screen_process(parameters=parameters)

    if tool in dispatch_map:
        return dispatch_map[tool]()

    if speak:
        speak("Bu görevi özel mantıkla işliyorum, efendim.")
    return _execute_dynamic_module(step.get("description", ""), speak)


class BrightExecutor:

    MAX_RETRIES = 2

    def execute(self, goal: str, speak: Callable | None = None, cancel_flag: threading.Event | None = None) -> str:
        print(f"\n[BrightOS] 🎯 Objective: {goal}")
        attempts = 0
        completed = []
        strategy = generate_strategy(goal)

        while True:
            phases = strategy.get("steps", [])
            if not phases: return "Strategy synthesis failed."

            success = True
            for phase in phases:
                if cancel_flag and cancel_flag.is_set():
                    return "Cancelled."

                print(f"\n[BrightOS] ▶️ Phase {phase.get('step')}: {phase.get('description')}")
                try:
                    result = _dispatch_tool(phase, speak)
                    print(f"[BrightOS] 🔧 Result: {result[:180]}")
                    completed.append(phase)
                except Exception as e:
                    print(f"[BrightOS] ⚠️ Phase failure: {e}")
                    if cancel_flag and cancel_flag.is_set():
                        return "Cancelled."
                    decision = analyze_error(phase, str(e), attempt=attempts + 1, max_attempts=self.MAX_RETRIES)
                    if decision["decision"] == ErrorDecision.RETRY and attempts < self.MAX_RETRIES:
                        attempts += 1
                        continue
                    if decision["decision"] == ErrorDecision.REPLAN:
                        strategy = refactor_strategy(goal, completed, phase, str(e))
                        success = False
                        break
                    return f"Operation aborted: {decision.get('user_message', 'Error')}."

            if success:
                return "Objective achieved."
            if attempts >= self.MAX_RETRIES:
                return "Task terminal failure."
            attempts += 1
            strategy = refactor_strategy(goal, completed, None, "Retry")
