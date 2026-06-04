#!/usr/bin/env python3
import os
import subprocess
import sys
import platform
import shutil

is_windows = platform.system() == "Windows"
is_macos = platform.system() == "Darwin"

# Define the path to the MCU directory
MCUPath = "MCU"

# Display/bundle name for the produced app (sets CFBundleName on macOS,
# the .exe name on Windows, and the binary name on Linux).
APP_NAME = "flash-tool"

# Initialize the options for PyInstaller
options = f'--windowed --name "{APP_NAME}" --add-data probes:probes'

if is_windows:
    options += " --onefile"
    options += " --add-data=tools/windows:tools/windows"
    options += " --icon=icon/icon.ico"
elif is_macos:
    options += " --onedir"
    options += " --add-data=tools/macos:tools/macos"
    options += " --icon=icon/icon.icns"
else:
    options += " --onefile"
    options += " --add-data=tools/linux:tools/linux"
    options += " --icon=icon/icon.png"

try:
    shutil.rmtree("dist")
except Exception:
    pass

# Get the list of subdirectories in the MCU directory
if os.path.exists(MCUPath):
    mcus = [name for name in os.listdir(MCUPath) if os.path.isdir(os.path.join(MCUPath, name))]

    # Loop through each MCU directory and add it to the PyInstaller options
    for m in mcus:
        mcu_dir = os.path.join(MCUPath, m)
        if os.path.isdir(mcu_dir):
            print(f"Adding MCU {m}")
            options += f" --add-data \"{mcu_dir}:{mcu_dir}\""
else:
    print(f"Error: The directory '{MCUPath}' does not exist.")
    sys.exit(1)

# Run PyInstaller with the accumulated options
try:
    subprocess.run(f"python3 -m PyInstaller {options} main.py", shell=True, check=True)
except subprocess.CalledProcessError as e:
    print(f"Error: PyInstaller failed with exit code {e.returncode}")
    sys.exit(1)

print("Success")
