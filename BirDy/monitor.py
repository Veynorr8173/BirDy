import os, json, time, math, random, threading
import tkinter as tk
from tkinter import messagebox
from collections import deque
import sys
from pathlib import Path

def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

BASE_DIR        = get_base_dir()
VAULT_DIR       = BASE_DIR / "security_vault"
API_FILE        = VAULT_DIR / "access.json"

SYSTEM_NAME     = "BİRDY — NEURAL ARCHIVE"
MODEL_BADGE     = "AUTHENTIC ARTIFICIAL INTELLIGENCE CORE"
DEVELOPER_CREDIT = "Designed by Veynor"

# THEME: DEEP SPACE JARVIS
C_BG      = "#010101"  # Pure Void
C_PRIMARY = "#00f2ff"  # Kinetic Cyan
C_SECONDARY = "#005a72" # Deep Slate Cyan
C_GLOW    = "#002a35"  # Faint Glow
C_TEXT    = "#f0f8ff"  # Ghost White
C_ALERT   = "#ff0055"  # System Alert Red

class BirDyUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{SYSTEM_NAME}")
        self.root.resizable(False, False)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        try:
            self.root.wm_attributes("-transparentcolor", C_BG)
        except Exception:
            pass

        # Floating round interface
        W, H = 720, 720
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")
        self.root.configure(bg=C_BG)

        self.W, self.H = W, H
        self.tick = 0
        self.speaking = False
        self.status_text = "HYPER-THREADING ACTIVE"
        self.typing_queue = deque()
        self.is_typing = False
        self.log_lines = deque(maxlen=6)
        self.drag_data = {"x": 0, "y": 0}
        
        # Sensory State
        self.visual_status = "AWARE"
        self.health_status = "STABLE"
        self.alert_text    = ""
        self.alert_timer   = 0

        self.canvas = tk.Canvas(self.root, width=W, height=H, bg=C_BG, highlightthickness=0)
        self.canvas.place(x=0, y=0)
        self.canvas.bind("<ButtonPress-1>", self._start_move)
        self.canvas.bind("<B1-Motion>", self._do_move)

        self.root.bind("<Escape>", lambda event: os._exit(0))

        self._api_key_ready = False
        if API_FILE.exists():
            try:
                with open(API_FILE, "r") as f:
                    data = json.load(f)
                    if data.get("gemini_api_key"):
                        self._api_key_ready = True
            except: pass

        if not self._api_key_ready:
            self.root.withdraw() 
            self._show_setup_ui()
        else:
            self._start_engine()

    def _start_engine(self):
        self.root.deiconify()
        self._animate()
        self.root.protocol("WM_DELETE_WINDOW", lambda: os._exit(0))

    def _animate(self):
        self.tick += 1
        self._draw()
        self.root.after(30, self._animate)

    def _draw(self):
        c = self.canvas
        c.delete("all")

        cx, cy = self.W // 2, self.H // 2
        t = self.tick

        # 1. Soft background circle body
        c.create_oval(20, 20, self.W-20, self.H-20, fill="#050d13", outline="#073544", width=5)
        c.create_oval(40, 40, self.W-40, self.H-40, outline="#0a3342", width=2)

        # 2. Core rings
        r1 = 250
        self._draw_arc_ring(cx, cy, r1, t * -0.4, 45, C_PRIMARY, 2)
        c.create_oval(cx-r1, cy-r1, cx+r1, cy+r1, outline="#053042", width=1)

        r2 = 200 + math.sin(t * 0.12) * 6
        self._draw_arc_ring(cx, cy, r2, t * 1.3, 100, C_PRIMARY, 3)
        c.create_oval(cx-r2, cy-r2, cx+r2, cy+r2, outline="#082d3c", width=2)

        r3 = 150
        for i in range(0, 360, 15):
            ang = math.radians(i + t * 0.9)
            x1 = cx + (r3-5) * math.cos(ang)
            y1 = cy + (r3-5) * math.sin(ang)
            x2 = cx + (r3+10) * math.cos(ang)
            y2 = cy + (r3+10) * math.sin(ang)
            c.create_line(x1, y1, x2, y2, fill=C_SECONDARY, width=2)

        c.create_oval(cx-100, cy-100, cx+100, cy+100, outline=C_PRIMARY, width=4)
        c.create_oval(cx-60, cy-60, cx+60, cy+60, outline=C_SECONDARY, width=3)

        # 3. Inner pulse
        inner_r = 30 + abs(math.sin(t * 0.3)) * 12
        c.create_oval(cx-inner_r, cy-inner_r, cx+inner_r, cy+inner_r, fill="#001920", outline=C_PRIMARY, width=2)

        # 4. Audio pulse lines
        line_r = 105
        for i in range(0, 360, 20):
            ang = math.radians(i)
            strength = 20 if self.speaking else 8
            offset = strength * (1 + math.sin(t * 0.2 + i)) / 2
            x1 = cx + (line_r-5) * math.cos(ang)
            y1 = cy + (line_r-5) * math.sin(ang)
            x2 = cx + (line_r+offset) * math.cos(ang)
            y2 = cy + (line_r+offset) * math.sin(ang)
            c.create_line(x1, y1, x2, y2, fill=C_PRIMARY, width=2)

        # 5. Subtle alert effect
        if self.alert_text:
            c.create_oval(cx-280, cy-280, cx+280, cy+280, outline=C_ALERT, width=2)
            c.create_oval(cx-260, cy-260, cx+260, cy+260, outline=C_ALERT, width=1)

    def _draw_arc_ring(self, cx, cy, r, start_ang, extent, color, width):
        # Arcs for a complex kinetic look
        self.canvas.create_arc(cx-r, cy-r, cx+r, cy+r, start=start_ang, extent=extent, outline=color, style="arc", width=width)
        self.canvas.create_arc(cx-r, cy-r, cx+r, cy+r, start=start_ang+180, extent=extent, outline=color, style="arc", width=width)

    def write_log(self, text: str):
        prefix = "»"
        if "You:" in text: text = text.replace("You:", "[USER] "); prefix = "◈"
        if "Jarvis:" in text: text = text.replace("Jarvis:", "[NEURAL] "); prefix = "❖"
        if "SYS:" in text: text = text.replace("SYS:", "[SYSTEM] "); prefix = "⚠"
        self.log_lines.append(f"{prefix} {text}")

    def _start_typing(self):
        if not self.typing_queue: self.is_typing = False; return
        self.is_typing = True
        line = self.typing_queue.popleft()
        
        # Professional formatting
        prefix = "»"
        if "You:" in line: line = line.replace("You:", "[USER] "); prefix = "◈"
        if "Jarvis:" in line: line = line.replace("Jarvis:", "[NEURAL] "); prefix = "❖"
        if "SYS:" in line: line = line.replace("SYS:", "[SYSTEM] "); prefix = "⚠"
        
        self.log_lines.append(f"{prefix} {line}")
        self.root.after(10, self._start_typing)

    def request_new_key(self, message="INVALID KEY DETECTED"):
        self._api_key_ready = False
        self.root.after(0, lambda: self._show_setup_ui(message))

    def _start_move(self, event):
        self.drag_data["x"] = event.x_root - self.root.winfo_x()
        self.drag_data["y"] = event.y_root - self.root.winfo_y()

    def _do_move(self, event):
        x = event.x_root - self.drag_data["x"]
        y = event.y_root - self.drag_data["y"]
        self.root.geometry(f"+{x}+{y}")

    def _show_setup_ui(self, custom_msg=None):
        win = tk.Toplevel()
        win.title("SYSTEM AUTHORIZATION REQUIRED")
        win.geometry("500x320")
        win.configure(bg=C_BG)
        win.resizable(False, False)
        win.attributes("-topmost", True)
        
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        win.geometry(f"500x320+{(sw-500)//2}+{(sh-320)//2}")

        tk.Label(win, text="◈ BİRDY NEURAL IGNITION", fg=C_PRIMARY, bg=C_BG, font=("Verdana", 14, "bold")).pack(pady=20)
        
        if custom_msg:
            tk.Label(win, text=custom_msg, fg=C_ALERT, bg=C_BG, font=("Consolas", 10, "bold")).pack()
            
        tk.Label(win, text="SECURE API MASTER KEY REQUIRED", fg=C_TEXT, bg=C_BG, font=("Consolas", 9)).pack(pady=5)
        
        e = tk.Entry(win, width=40, show="*", bg="#05080a", fg=C_PRIMARY, insertbackground=C_PRIMARY, font=("Consolas", 10))
        e.pack(pady=10)
        e.focus_set()

        def save(evt=None):
            key = e.get().strip()
            if key:
                try:
                    current_data = {}
                    if API_FILE.exists():
                        try:
                            with open(API_FILE, "r") as f: current_data = json.load(f)
                        except: pass
                    current_data["gemini_api_key"] = key
                    VAULT_DIR.mkdir(parents=True, exist_ok=True)
                    with open(API_FILE, "w") as f: json.dump(current_data, f)
                    win.destroy()
                    self._api_key_ready = True
                    self._start_engine()
                except Exception as ex:
                    messagebox.showerror("VAULT ERROR", f"Security breach writing to vault: {ex}")

        btn = tk.Button(win, text="[ AUTHORIZE CORE ]", command=save, bg="#0a1014", fg=C_PRIMARY, 
                        activebackground=C_PRIMARY, activeforeground=C_BG, borderwidth=1, relief="flat", padx=20, pady=10)
        btn.pack(pady=20)
        win.bind("<Return>", save)
        win.protocol("WM_DELETE_WINDOW", lambda: os._exit(0))

    def start_speaking(self): self.speaking = True; self.status_text = "HYPER-STREAM DATA INJECT"
    def stop_speaking(self): self.speaking = False; self.status_text = "READY FOR SIGNAL"

    def show_proactive_alert(self, text: str):
        self.alert_text = text
        self.root.after(5000, lambda: setattr(self, "alert_text", ""))

    def update_sensory(self, vision="AWARE", health="STABLE"):
        self.visual_status = vision
        self.health_status = health

    def wait_for_api_key(self):
        while not self._api_key_ready: time.sleep(0.1)

if __name__ == "__main__":
    ui = BirDyUI()
    ui.root.mainloop()
