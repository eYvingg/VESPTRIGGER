import tkinter as tk
import customtkinter as ctk
from PIL import ImageGrab, ImageTk, Image
import keyboard
import threading
import time
import json
import mss  
import numpy as np 
import ctypes

# DPI Awareness
ctypes.windll.shcore.SetProcessDpiAwareness(1)

# Win32 Mouse
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

def win32_click_down():
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)

def win32_click_up():
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

ctk.set_appearance_mode("dark")
root = ctk.CTk()
root.title("VESP TRIGGER")
root.geometry("400x900")
root.attributes("-topmost", True)
root.configure(fg_color="#0a0a0a")

# Глобальные переменные
TARGET_COLOR = (255, 0, 0)
IS_ACTIVE = False
TOGGLE_KEY = 'f6'
CURRENT_HOOK = None
SCAN_AREA = None 
CHECK_INTERVAL = 0.001 
MODE = "Hold" 
IS_HOLDING = False 
COOLDOWN_SINGLE = False 
TOLERANCE = 35

def add_log(msg):
    log_box.configure(state="normal")
    log_box.insert("end", f"{msg}\n")
    log_box.see("end")
    log_box.configure(state="disabled")

def hex_to_rgb(value):
    value = value.lstrip('#')
    return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))

def update_status_ui():
    color = "#ff1a1a" if IS_ACTIVE else "#222222"
    status_dot.configure(fg_color=color)
    text = "SYSTEM: ACTIVE" if IS_ACTIVE else "SYSTEM: STANDBY"
    status_label.configure(text=text, text_color="#ff1a1a" if IS_ACTIVE else "#444444")

def toggle_script():
    global IS_ACTIVE, IS_HOLDING, COOLDOWN_SINGLE
    if SCAN_AREA is None: return
    IS_ACTIVE = not IS_ACTIVE
    COOLDOWN_SINGLE = False
    if not IS_ACTIVE and IS_HOLDING:
        win32_click_up()
        IS_HOLDING = False
    update_status_ui()

def clicker_loop():
    global IS_HOLDING, COOLDOWN_SINGLE
    with mss.mss() as sct:
        while True:
            if IS_ACTIVE and SCAN_AREA:
                start_time = time.perf_counter()
                
                monitor = {
                    "top": int(SCAN_AREA[1]),
                    "left": int(SCAN_AREA[0]),
                    "width": int(SCAN_AREA[2] - SCAN_AREA[0]),
                    "height": int(SCAN_AREA[3] - SCAN_AREA[1])
                }
                
                sct_img = sct.grab(monitor)
                img_np = np.frombuffer(sct_img.bgra, dtype=np.uint8).reshape(sct_img.height, sct_img.width, 4)
                target_bgr = np.array([TARGET_COLOR[2], TARGET_COLOR[1], TARGET_COLOR[0]], dtype=np.int16)
                bgr_pixels = img_np[:, :, :3].astype(np.int16)
                diff = np.abs(bgr_pixels - target_bgr)
                match = np.any(np.all(diff <= TOLERANCE, axis=-1))
                
                if match:
                    r_time = (time.perf_counter() - start_time) * 1000
                    if MODE == "Hold":
                        if not IS_HOLDING:
                            win32_click_down()
                            IS_HOLDING = True
                            add_log(f"HOLD START | {r_time:.2f}ms")
                    elif MODE == "Single":
                        if not COOLDOWN_SINGLE:
                            win32_click_down()
                            time.sleep(0.01)
                            win32_click_up()
                            COOLDOWN_SINGLE = True
                            add_log(f"SHOT | {r_time:.2f}ms")
                else:
                    if IS_HOLDING:
                        win32_click_up()
                        IS_HOLDING = False
                        add_log("HOLD RELEASE")
                    COOLDOWN_SINGLE = False
            
            time.sleep(CHECK_INTERVAL)

def record_key():
    bind_btn.configure(text="PRESS KEY...", fg_color="#330000")
    def capture():
        global TOGGLE_KEY, CURRENT_HOOK
        combo = keyboard.read_hotkey(suppress=False)
        if CURRENT_HOOK is not None:
            try: keyboard.remove_hotkey(CURRENT_HOOK)
            except: pass
        TOGGLE_KEY = combo.lower()
        CURRENT_HOOK = keyboard.add_hotkey(TOGGLE_KEY, toggle_script)
        bind_btn.configure(text=TOGGLE_KEY.upper(), fg_color="#1a1a1a")
    threading.Thread(target=capture, daemon=True).start()

def update_bind(key_string):
    global TOGGLE_KEY, CURRENT_HOOK
    if CURRENT_HOOK:
        try: keyboard.remove_hotkey(CURRENT_HOOK)
        except: pass
    TOGGLE_KEY = key_string.lower()
    CURRENT_HOOK = keyboard.add_hotkey(TOGGLE_KEY, toggle_script)

def save_config():
    config = {
        "hex": color_entry.get(), 
        "area": SCAN_AREA, 
        "key": TOGGLE_KEY, 
        "mode": MODE, 
        "tol": TOLERANCE
    }
    with open("config.json", "w") as f: json.dump(config, f)
    add_log("Config Saved")

def load_config():
    global SCAN_AREA, TARGET_COLOR, MODE, TOGGLE_KEY, TOLERANCE
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
            color_entry.delete(0, tk.END); color_entry.insert(0, config["hex"]); apply_hex_color()
            SCAN_AREA = tuple(config["area"]) if config.get("area") else None
            if SCAN_AREA: area_label.configure(text=f"AREA: {SCAN_AREA[2]-SCAN_AREA[0]}x{SCAN_AREA[3]-SCAN_AREA[1]} PX")
            TOGGLE_KEY = config.get("key", "f6"); bind_btn.configure(text=TOGGLE_KEY.upper()); update_bind(TOGGLE_KEY)
            TOLERANCE = config.get("tol", 35); tol_slider.set(TOLERANCE); tol_val_label.configure(text=f"TOLERANCE: {TOLERANCE}")
            set_mode(config.get("mode", "Hold"))
    except: update_bind("f6")

def set_mode(new_mode):
    global MODE, IS_HOLDING, COOLDOWN_SINGLE
    if IS_HOLDING: win32_click_up(); IS_HOLDING = False
    COOLDOWN_SINGLE = False; MODE = new_mode
    mode_label.configure(text=f"MODE: {MODE.upper()}")

def select_zone():
    root.iconify()
    time.sleep(0.2)
    selector = tk.Toplevel(root); selector.attributes("-fullscreen", True, "-topmost", True, "-alpha", 0.3); selector.config(bg="black")
    canvas = tk.Canvas(selector, cursor="cross", bg="black", highlightthickness=0); canvas.pack(fill="both", expand=True)
    
    # Инициализация переменных ДО функций on_press/on_release
    sel_data = {"start_x": 0, "start_y": 0, "rect": None}

    def on_press(e):
        sel_data["start_x"], sel_data["start_y"] = e.x, e.y
        sel_data["rect"] = canvas.create_rectangle(e.x, e.y, e.x, e.y, outline="red", width=2)

    def on_drag(e):
        if sel_data["rect"]: canvas.coords(sel_data["rect"], sel_data["start_x"], sel_data["start_y"], e.x, e.y)

    def on_release(e):
        global SCAN_AREA
        SCAN_AREA = (min(sel_data["start_x"], e.x), min(sel_data["start_y"], e.y), max(sel_data["start_x"], e.x), max(sel_data["start_y"], e.y))
        area_label.configure(text=f"AREA: {SCAN_AREA[2]-SCAN_AREA[0]}x{SCAN_AREA[3]-SCAN_AREA[1]} PX")
        selector.destroy(); root.deiconify()

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)

def start_color_picker():
    screenshot = ImageGrab.grab()
    picker = tk.Toplevel(root); picker.attributes("-fullscreen", True, "-topmost", True); picker.config(cursor="cross")
    img_tk = ImageTk.PhotoImage(screenshot); canvas = tk.Canvas(picker, highlightthickness=0); canvas.pack(fill="both", expand=True)
    canvas.create_image(0, 0, anchor="nw", image=img_tk); canvas.image = img_tk
    p_w, p_h = 70, 28
    c_p_box = canvas.create_rectangle(0, 0, p_w, p_h, outline="white", width=1, fill="#000000")
    c_text = canvas.create_text(5, 14, anchor="w", fill="white", font=("Consolas", 11, "bold"), text="#000000")
    def on_move(event):
        if not (0 <= event.x < screenshot.width and 0 <= event.y < screenshot.height): return
        rgb = screenshot.getpixel((event.x, event.y)); hex_c = '#%02x%02x%02x' % rgb
        px, py = event.x + 20, event.y + 20
        canvas.coords(c_p_box, px, py, px + p_w, py + p_h)
        canvas.coords(c_text, px + 5, py + p_h // 2)
        canvas.itemconfig(c_p_box, fill=hex_c); canvas.itemconfig(c_text, text=hex_c)
    def on_click(event):
        global TARGET_COLOR; rgb = screenshot.getpixel((event.x, event.y)); TARGET_COLOR = rgb
        hex_c = '#%02x%02x%02x' % rgb
        color_entry.delete(0, tk.END); color_entry.insert(0, hex_c); apply_hex_color(); picker.destroy()
    canvas.bind("<Motion>", on_move); canvas.bind("<Button-1>", on_click)

def apply_hex_color():
    global TARGET_COLOR
    try: TARGET_COLOR = hex_to_rgb(color_entry.get()); color_preview.configure(fg_color=color_entry.get())
    except: pass

# --- UI --- 
f_top = ctk.CTkFrame(root, fg_color="transparent")
f_top.pack(pady=(30, 0))
status_dot = ctk.CTkFrame(f_top, width=12, height=12, corner_radius=6, fg_color="#222222")
status_dot.pack(side="left", padx=10)
header = ctk.CTkLabel(f_top, text="VESP TRIGGER", font=("Impact", 42), text_color="#ff1a1a")
header.pack(side="left")

status_label = ctk.CTkLabel(root, text="SYSTEM: STANDBY", text_color="#444444", font=("Consolas", 16, "bold"))
status_label.pack(pady=10)

f_mode = ctk.CTkFrame(root, fg_color="#111111", corner_radius=15, border_width=1, border_color="#222222")
f_mode.pack(pady=10, padx=25, fill="x")
mode_label = ctk.CTkLabel(f_mode, text=f"MODE: {MODE.upper()}", font=("Consolas", 14, "bold"), text_color="#eeeeee")
mode_label.pack(pady=10)
ctk.CTkButton(f_mode, text="HOLD", height=32, fg_color="#1a1a1a", border_width=1, border_color="#440000", command=lambda: set_mode("Hold")).pack(side="left", padx=10, pady=10, expand=True)
ctk.CTkButton(f_mode, text="SINGLE", height=32, fg_color="#1a1a1a", border_width=1, border_color="#440000", command=lambda: set_mode("Single")).pack(side="right", padx=10, pady=10, expand=True)

f_zone = ctk.CTkFrame(root, fg_color="#111111", corner_radius=15, border_width=1, border_color="#222222")
f_zone.pack(pady=10, padx=25, fill="x")
ctk.CTkButton(f_zone, text="SELECT SCAN AREA", fg_color="#ff1a1a", hover_color="#b30000", font=("Arial", 12, "bold"), command=select_zone).pack(pady=15, padx=20, fill="x")
area_label = ctk.CTkLabel(f_zone, text="NO AREA DEFINED", font=("Consolas", 11), text_color="#666666")
area_label.pack(pady=(0, 15))

f_tol = ctk.CTkFrame(root, fg_color="#111111", corner_radius=15, border_width=1, border_color="#222222")
f_tol.pack(pady=10, padx=25, fill="x")
tol_val_label = ctk.CTkLabel(f_tol, text=f"TOLERANCE: {TOLERANCE}", font=("Consolas", 12))
tol_val_label.pack(pady=5)
tol_slider = ctk.CTkSlider(f_tol, from_=1, to=100, fg_color="#222222", progress_color="#ff1a1a", button_color="#ff1a1a", command=lambda v: (globals().update(TOLERANCE=int(v)), tol_val_label.configure(text=f"TOLERANCE: {int(v)}")))

tol_slider.set(TOLERANCE); tol_slider.pack(pady=10, padx=20)

f_color = ctk.CTkFrame(root, fg_color="#111111", corner_radius=15, border_width=1, border_color="#222222")
f_color.pack(pady=10, padx=25, fill="x")
color_preview = ctk.CTkFrame(f_color, width=120, height=8, fg_color="#FF0000")
color_preview.pack(pady=(15, 5))
color_entry = ctk.CTkEntry(f_color, fg_color="#000000", border_color="#333333", justify="center")
color_entry.insert(0, "#FF0000"); color_entry.pack(pady=5, padx=20, fill="x")
ctk.CTkButton(f_color, text="PICK COLOR", command=start_color_picker, fg_color="transparent", border_width=1, border_color="#333333").pack(pady=15, padx=20, fill="x")

f_bot = ctk.CTkFrame(root, fg_color="transparent")
f_bot.pack(pady=10, padx=25, fill="x")
bind_btn = ctk.CTkButton(f_bot, text="RECORD KEY", width=120, fg_color="#1a1a1a", border_width=1, border_color="#333333", command=record_key)
bind_btn.pack(side="left")
ctk.CTkButton(f_bot, text="SAVE", width=60, fg_color="#1a1a1a", text_color="#4CAF50", border_width=1, border_color="#2b5e2b", command=save_config).pack(side="right", padx=2)
ctk.CTkButton(f_bot, text="LOAD", width=60, fg_color="#1a1a1a", text_color="#f44336", border_width=1, border_color="#5e2b2b", command=load_config).pack(side="right", padx=2)

log_box = ctk.CTkTextbox(root, height=100, fg_color="#050505", text_color="#00ff00", font=("Consolas", 11)); log_box.pack(pady=10, padx=25, fill="x"); log_box.configure(state="disabled")

load_config()
threading.Thread(target=clicker_loop, daemon=True).start()
root.mainloop()
