#!/usr/bin/env python3
'''
UI for unlocking ESC MCUs for AM32 project
'''

VERSION = "1.0"
PROBE = "stlink"
MCU_LIST = ["H7x", "G0x", "L4x", "F421"]

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog
import subprocess
import os
import sys
import threading
import time
import shutil
from datetime import datetime
import intelhex
import locale
import platform
import tempfile

is_windows = platform.system() == "Windows"
is_macos = platform.system() == "Darwin"

TRANSLATIONS = {
    "en": {
        "select_mcu": "Select MCU Type:",
        "start": "Start",
        "stop": "Stop",
        "quit": "Quit",
        "firmware": "Full Firmware:",
        "browse": "Browse...",
        "select_firmware": "Full Firmware",
        "warning": (
            "Select the right MCU:\n"
            "MCU Type H7x -> Align Flight Controller (AP6-AP6mini)\n"
            "MCU Type G0x -> Align Mower and LED Panel\n"
            "MCU Type L4x -> Align ESC and PCU\n"
            "MCU Type F421 -> 4-in-1 (M3-M450-M460-M490)"
        ),
        "lang_btn": "中文",
    },
    "zh_TW": {
        "select_mcu": "選擇 MCU 類型:",
        "start": "開始",
        "stop": "停止",
        "quit": "退出程式",
        "firmware": "完整韌體:",
        "browse": "瀏覽...",
        "select_firmware": "完整韌體",
        "warning": (
            "請選擇正確的 MCU：\n"
            "MCU 類型 H7x -> Align 飛控（AP6-AP6mini）\n"
            "MCU 類型 G0x -> Align 割草機與 LED 面板\n"
            "MCU 類型 L4x -> Align ESC 與 PCU\n"
            "MCU 類型 F421 -> 四合一（M3-M450-M460-M490）"
        ),
        "lang_btn": "English",
    },
}


def get_system_language():
    """Detect system language and return 'zh_TW' or 'en'."""
    try:
        system_locale = locale.getlocale()[0]
        if not system_locale:
            system_locale = os.environ.get('LANG', '') or os.environ.get('LC_ALL', '')
        if system_locale and system_locale.lower().startswith('zh'):
            return 'zh_TW'
    except Exception:
        pass
    return 'en'


current_lang = get_system_language()


def tr(key):
    return TRANSLATIONS.get(current_lang, {}).get(key, key)


def log_message(msg):
    '''append to the log'''
    try:
        tstr = datetime.now().strftime("%c")
        f = open("esc_unlocker.log", "a")
        f.write(tstr + "\n")
        f.write(msg)
        f.write("\n")
        f.close()
    except Exception:
        pass

def get_resource_path(relative_path):
    """ Get the absolute path to a resource, works for development and PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")

    ret = os.path.join(base_path, relative_path)
    if is_windows:
        # cope with windows paths
        ret = ret.replace("\\", "\\\\")
    return ret


def get_openocd():
    '''get path to openocd'''
    if is_windows:
        return get_resource_path("tools/windows/openocd/bin/openocd.exe")
    elif is_macos:
        bundled = get_resource_path("tools/macos/openocd/bin/openocd")
        if os.path.exists(bundled):
            try:
                subprocess.run([bundled, "--version"], capture_output=True, timeout=5)
                return bundled
            except (OSError, subprocess.SubprocessError):
                pass
        system = shutil.which("openocd")
        if system:
            print(f"Bundled OpenOCD not usable, falling back to system: {system}")
            return system
        raise FileNotFoundError("OpenOCD not found. Please install it (e.g. brew install openocd)")
    else:
        return get_resource_path("tools/linux/openocd/bin/openocd")

def run_openocd():
    '''
    run openocd as a child, looping until running is False or success
    '''
    global running
    running = True
    mcu_type = mcu_var.get()
    probe_type = PROBE

    if mcu_type.find("_") != -1:
        mcu_base = mcu_type.split('_')[0]
        k_tag = "_" + mcu_type.split('_')[1]
    else:
        mcu_base = mcu_type
        k_tag = ''
    config_file = f"MCU/{mcu_base}/openocd-unlock.cfg"
    probe_file = get_resource_path(f"probes/{probe_type}.cfg")

    config_file = get_resource_path(config_file)
    custom_bootloader = bootloader_var.get()

    if custom_bootloader:
        bootloader = custom_bootloader
    else:
        log_message("Error: no firmware selected")
        return

    log_message("Starting MCU %s flash" % mcu_type)

    using_tempfile = False

    if bootloader.lower().endswith(".hex"):
        thandle = tempfile.NamedTemporaryFile(delete=False, suffix=".bin")
        tfile = thandle.name
        print("CREATED '%s'" % tfile)
        if intelhex.hex2bin(bootloader, tfile) != 0:
            log_message("Failed to convert hex to bin")
            return
        bootloader = tfile
        using_tempfile = True
        if is_windows:
            bootloader = bootloader.replace("\\", "\\\\")

    print("Using config file '%s'" % config_file)
    print("Using probe file '%s'" % probe_file)
    while running:
        try:

            if is_windows:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            else:
                startupinfo = None

            openocd = get_openocd()
            process = subprocess.Popen([openocd,
                                        '-c', 'set BOOTLOADER "%s"' % bootloader,
                                        '--file', probe_file,
                                        '--file', config_file],
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE,
                                        startupinfo=startupinfo)

            output = process.stdout.read().decode()
            if output:
                root.after(0, lambda t=output: (output_text.insert(tk.END, t), output_text.see(tk.END)))
                log_message(output)
            outerr = process.stderr.read().decode()
            if outerr:
                root.after(0, lambda t=outerr: (output_text.insert(tk.END, t), output_text.see(tk.END)))
                log_message(outerr)
            if outerr.find("Cortex-M") != -1:
                # found the MCU
                root.after(0, lambda: update_status_led("orange"))
            else:
                # we're still looking for the MCU
                root.after(0, lambda: update_status_led("red"))
            retcode = process.poll()
            if retcode is not None:
                if retcode == 0:
                    log_message("Success")
                    print("Flash successful.")
                    root.after(0, lambda: update_status_led("green"))
                    running = False
        except Exception as e:
            print(f"Error running OpenOCD: {e}")

    if using_tempfile:
        os.unlink(tfile)

def start_openocd():
    if not running:
        output_text.delete(1.0, tk.END)
        thd = threading.Thread(target=run_openocd)
        thd.start()

def stop_openocd():
    global running
    running = False
    log_message("stopping")

def quit():
    global running
    running = False
    sys.exit(0)

def update_status_led(color):
    canvas.itemconfig(led, fill=color)

def toggle_language():
    global current_lang
    current_lang = "zh_TW" if current_lang == "en" else "en"
    update_all_texts()

def update_all_texts():
    mcu_label.config(text=tr("select_mcu"))
    start_button.config(text=tr("start"))
    stop_button.config(text=tr("stop"))
    quit_button.config(text=tr("quit"))
    bootloader_label.config(text=tr("firmware"))
    bootloader_button.config(text=tr("browse"))
    warn.config(text=tr("warning"))
    lang_btn.config(text=tr("lang_btn"))

def select_bootloader_file():
    file_path = filedialog.askopenfilename(title=tr("select_firmware"), filetypes=[("Bin and hex files", "*.bin *.hex"), ("All files", "*.*")])
    if file_path:
        bootloader_var.set(file_path)


# Initialize GUI
root = tk.Tk()
root.title(f"Align Flash Tool v{VERSION}")

root.grid_rowconfigure(7, weight=1)
root.grid_columnconfigure(0, weight=1)
root.grid_columnconfigure(1, weight=1)
root.grid_columnconfigure(2, weight=1)
root.grid_columnconfigure(3, weight=1)

# MCU type selection
mcu_var = tk.StringVar()
mcu_label = ttk.Label(root, text=tr("select_mcu"))
mcu_label.grid(row=0, column=0, padx=10, pady=10)
mcu_dropdown = ttk.OptionMenu(root, mcu_var, MCU_LIST[0], *MCU_LIST)
mcu_dropdown.grid(row=0, column=1, padx=10, pady=10)

# Language toggle button
lang_btn = ttk.Button(root, text=tr("lang_btn"), command=toggle_language)
lang_btn.grid(row=0, column=3, padx=10, pady=10)

# Start and Stop buttons
start_button = ttk.Button(root, text=tr("start"), command=start_openocd)
start_button.grid(row=2, column=1, padx=10, pady=10)
stop_button = ttk.Button(root, text=tr("stop"), command=stop_openocd)
stop_button.grid(row=2, column=2, padx=10, pady=10)

quit_button = ttk.Button(root, text=tr("quit"), command=quit)
quit_button.grid(row=2, column=3, padx=10, pady=10)

# Status LED
canvas = tk.Canvas(root, width=20, height=20)
canvas.grid(row=2, column=0, columnspan=1, pady=10)
led = canvas.create_oval(5, 5, 20, 20, fill="gray")

# Custom Bootloader selection
bootloader_var = tk.StringVar()
bootloader_label = ttk.Label(root, text=tr("firmware"))
bootloader_label.grid(row=5, column=0, padx=10, pady=10)
bootloader_entry = ttk.Entry(root, textvariable=bootloader_var, width=40)
bootloader_entry.grid(row=5, column=1, columnspan=2, padx=10, pady=10)
bootloader_button = ttk.Button(root, text=tr("browse"), command=select_bootloader_file)
bootloader_button.grid(row=5, column=3, padx=10, pady=10)

warn = ttk.Label(root, text=tr("warning"), justify=tk.LEFT)
warn.grid(row=6, column=0, columnspan=4, padx=10, pady=10, sticky="w")

output_text = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=50, height=10)
output_text.grid(row=7, column=0, columnspan=4, padx=10, pady=10, sticky="nsew")

running = False

# Start the GUI event loop
root.mainloop()
