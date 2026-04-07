#!/usr/bin/env python3
'''
UI for unlocking ESC MCUs for AM32 project
'''

VERSION = "0.2"
PROBE_LIST = ["ST Link", "JLink", "CMSIS-DAP"]
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

import platform
import tempfile

is_windows = platform.system() == "Windows"
is_macos = platform.system() == "Darwin"


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
    probe_type = probe_var.get()
    if probe_type == "ST Link":
        probe_type = "stlink"
    elif probe_type == "JLink":
        probe_type = "jlink"
    elif probe_type == "CMSIS-DAP":
        probe_type = "cmsis-dap"

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

# Initialize GUI
root = tk.Tk()
root.title(f"Align Flash Tool v{VERSION}")

root.grid_rowconfigure(7, weight=1)
root.grid_columnconfigure(0, weight=1)
root.grid_columnconfigure(1, weight=1)
root.grid_columnconfigure(2, weight=1)
root.grid_columnconfigure(3, weight=1)

# Probe selection
probe_var = tk.StringVar()
probe_label = ttk.Label(root, text="Select Probe:")
probe_label.grid(row=0, column=2, padx=10, pady=10)
probe_dropdown = ttk.OptionMenu(root, probe_var, PROBE_LIST[0], *PROBE_LIST)
probe_dropdown.grid(row=0, column=3, padx=10, pady=10)

# MCU type selection
mcu_var = tk.StringVar()
mcu_label = ttk.Label(root, text="Select MCU Type:")
mcu_label.grid(row=0, column=0, padx=10, pady=10)
mcu_dropdown = ttk.OptionMenu(root, mcu_var, MCU_LIST[0], *MCU_LIST)
mcu_dropdown.grid(row=0, column=1, padx=10, pady=10)

# Start and Stop buttons
start_button = ttk.Button(root, text="Start", command=start_openocd)
start_button.grid(row=2, column=1, padx=10, pady=10)
stop_button = ttk.Button(root, text="Stop", command=stop_openocd)
stop_button.grid(row=2, column=2, padx=10, pady=10)

stop_button = ttk.Button(root, text="Quit", command=quit)
stop_button.grid(row=2, column=3, padx=10, pady=10)

# Status LED
canvas = tk.Canvas(root, width=20, height=20)
canvas.grid(row=2, column=0, columnspan=1, pady=10)
led = canvas.create_oval(5, 5, 20, 20, fill="gray")

# Custom Bootloader selection
def select_bootloader_file():
    file_path = filedialog.askopenfilename(title="Full Firmware", filetypes=[("Bin and hex files", "*.bin *.hex"), ("All files", "*.*")])
    if file_path:
        bootloader_var.set(file_path)

bootloader_var = tk.StringVar()
bootloader_label = ttk.Label(root, text="Full Firmware:")
bootloader_label.grid(row=5, column=0, padx=10, pady=10)
bootloader_entry = ttk.Entry(root, textvariable=bootloader_var, width=40)
bootloader_entry.grid(row=5, column=1, columnspan=2, padx=10, pady=10)
bootloader_button = ttk.Button(root, text="Browse...", command=select_bootloader_file)
bootloader_button.grid(row=5, column=3, padx=10, pady=10)
warning_txt = """Select the right MCU:
MCU Type H7x -> Align Flight Controller (AP6-AP6mini)
MCU Type G0x -> Align Mower
MCU Type L4x -> Align custom CAN ESC (M450-M460-M490)
MCU Type F421 -> 4-in-1 (M3-M450-M460-M490)
"""
warn = ttk.Label(root, text=warning_txt, justify=tk.LEFT)
warn.grid(row=6, column=0, columnspan=4, padx=10, pady=10, sticky="w")


output_text = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=50, height=10)
output_text.grid(row=7, column=0, columnspan=4, padx=10, pady=10, sticky="nsew")

running = False

# Start the GUI event loop
root.mainloop()
