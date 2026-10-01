#!/usr/bin/env python3
"""
DisWhisper Automated Dependency & Environment Verification Script.
Checks Python version, FFmpeg binary, NVIDIA GPU/CUDA, and installs python dependencies.
"""

import os
import platform
import shutil
import subprocess
import sys

# Ensure stdout and stderr handle unicode characters across all terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_step(title: str):
    print(f"\n{BOLD}{CYAN}==> {title}{RESET}")


def check_python() -> bool:
    print_step("Checking Python Version")
    v = sys.version_info
    print(f"Current Python: {platform.python_version()} ({sys.executable})")
    if v.major == 3 and v.minor >= 10:
        print(f"{GREEN}[OK] Python version 3.10+ detected.{RESET}")
        return True
    else:
        print(f"{RED}[FAIL] Python 3.10 or higher is required. Please upgrade.{RESET}")
        return False


def check_ffmpeg() -> bool:
    print_step("Checking FFmpeg Availability")
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        try:
            res = subprocess.run(
                ["ffmpeg", "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            first_line = res.stdout.splitlines()[0] if res.stdout else "Available"
            print(f"{GREEN}[OK] FFmpeg found at: {ffmpeg_path}{RESET}")
            print(f"     Version info: {first_line}")
            return True
        except Exception as e:
            print(f"{YELLOW}[WARN] ffmpeg found but execution failed: {e}{RESET}")
            return False
    else:
        print(f"{RED}[FAIL] FFmpeg is not found in your system PATH.{RESET}")
        print("FFmpeg is optional for this PCM voice pipeline; install it if other audio tools need it.")
        if platform.system() == "Windows":
            print(f"{YELLOW}Windows install options:{RESET}")
            print("  1. winget install Gyan.FFmpeg")
            print("  2. choco install ffmpeg")
            print("  3. Download from https://www.gyan.dev/ffmpeg/builds/ and add bin/ to PATH")
        elif platform.system() == "Linux":
            print(f"{YELLOW}Linux install option:{RESET}")
            print("  sudo apt-get update && sudo apt-get install -y ffmpeg")
        elif platform.system() == "Darwin":
            print(f"{YELLOW}macOS install option:{RESET}")
            print("  brew install ffmpeg")
        return False


def check_cuda() -> bool:
    print_step("Checking NVIDIA GPU & CUDA")
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        try:
            res = subprocess.run(
                [nvidia_smi, "--query-gpu=gpu_name,memory.total,driver_version", "--format=csv,noheader"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            info = res.stdout.strip()
            print(f"{GREEN}[OK] NVIDIA GPU detected: {info}{RESET}")
            return True
        except Exception as e:
            print(f"{YELLOW}[WARN] nvidia-smi failed: {e}{RESET}")
            return False
    else:
        print(f"{YELLOW}[WARN] nvidia-smi not found. CUDA acceleration may not be available.{RESET}")
        print("SenseVoice, Vosk, and smaller Whisper models can run on CPU. Larger Whisper models benefit from a GPU.")
        return False


def install_requirements() -> bool:
    print_step("Installing Python Dependencies from requirements.txt")
    req_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "requirements.txt")
    if not os.path.exists(req_file):
        print(f"{RED}[FAIL] requirements.txt not found at {req_file}{RESET}")
        return False

    cmd = [sys.executable, "-m", "pip", "install", "-r", req_file]
    print(f"Running: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
        print(f"{GREEN}[OK] Dependencies successfully installed!{RESET}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"{RED}[FAIL] pip installation failed with exit code {e.returncode}{RESET}")
        return False


def verify_libraries():
    print_step("Verifying Core Imports")
    # Ensure stdout/stderr handle UTF-8 cleanly on Windows
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    libs = [
        ("discord", "discord.py"),
        ("discord.ext.voice_recv", "discord-ext-voice-recv"),
        ("faster_whisper", "faster-whisper"),
        ("ctranslate2", "ctranslate2"),
        ("sherpa_onnx", "sherpa-onnx"),
        ("vosk", "vosk"),
        ("davey", "DAVE encrypted voice support"),
        ("aiohttp", "companion API"),
        ("huggingface_hub", "model downloads"),
        ("numpy", "numpy"),
        ("pydantic", "pydantic"),
    ]
    all_ok = True
    for module_name, display_name in libs:
        try:
            __import__(module_name)
            print(f"  {GREEN}[OK]{RESET} {display_name}")
        except Exception as e:
            print(f"  {RED}[FAIL]{RESET} {display_name}: {e}")
            all_ok = False

    if all_ok:
        try:
            import ctranslate2
            cuda_count = ctranslate2.get_cuda_device_count()
            print(f"\n{GREEN}[OK] CTranslate2 detected {cuda_count} CUDA device(s).{RESET}")
        except Exception as e:
            print(f"{YELLOW}[WARN] Could not query CTranslate2 CUDA devices: {e}{RESET}")

    return all_ok


def main():
    print(f"{BOLD}{GREEN}=========================================={RESET}")
    print(f"{BOLD}{GREEN}  DisWhisper Pre-flight & Setup Checker   {RESET}")
    print(f"{BOLD}{GREEN}=========================================={RESET}")

    py_ok = check_python()
    check_ffmpeg()
    check_cuda()

    if not py_ok:
        sys.exit(1)

    install_ok = install_requirements()
    if not install_ok:
        print(f"\n{RED}Dependency installation failed. Please review errors above.{RESET}")
        sys.exit(1)

    verify_ok = verify_libraries()

    print(f"\n{BOLD}{CYAN}------------------------------------------{RESET}")
    if verify_ok:
        print(f"{BOLD}{GREEN}All checks passed! DisWhisper is ready to run.{RESET}")
        print("To configure, copy .env.example to .env and insert your DISCORD_TOKEN.")
        print("Then run: python -m diswhisper.main")
    else:
        print(f"{BOLD}{YELLOW}Setup completed with warnings. Review missing items before running.{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
