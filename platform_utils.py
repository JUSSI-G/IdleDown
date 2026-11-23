import subprocess
import sys

try:
    import pynvml
except ImportError:
    pynvml = None


def find_nvidia_gpus():
    if pynvml is None:
        return []
    try:
        pynvml.nvmlInit()
        gpu_count = pynvml.nvmlDeviceGetCount()
        return [pynvml.nvmlDeviceGetHandleByIndex(index) for index in range(gpu_count)]
    except pynvml.NVMLError:
        return []


def get_gpu_usage(gpus):
    if not gpus:
        return None
    try:
        return max(pynvml.nvmlDeviceGetUtilizationRates(gpu).gpu for gpu in gpus)
    except pynvml.NVMLError:
        return None


def get_shutdown_command():
    if sys.platform == "win32":
        return ["shutdown", "/s", "/t", "0"]
    if sys.platform == "darwin":
        return ["osascript", "-e", 'tell application "System Events" to shut down']
    return ["systemctl", "poweroff"]


def shutdown_computer():
    subprocess.run(get_shutdown_command(), check=True)