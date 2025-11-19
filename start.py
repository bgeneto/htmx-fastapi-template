#!/usr/bin/env python3
"""
Simple startup script for the Alpine + FastAPI application
"""
import os
import subprocess
import sys
from pathlib import Path


def kill_existing_processes():
    """Kill any existing uvicorn processes that might be using port 8000"""
    import signal

    try:
        # First, try to kill processes listening on port 8000
        result = subprocess.run(
            ["lsof", "-i", ":8000"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            # Found processes, extract PIDs and kill them
            lines = result.stdout.strip().split("\n")[1:]  # Skip header
            pids = []
            for line in lines:
                parts = line.split()
                if len(parts) > 1 and parts[0] in ["COMMAND", "python", "uvicorn"]:
                    try:
                        pid = int(parts[1])
                        pids.append(pid)
                    except (ValueError, IndexError):
                        continue

            if pids:
                print(f"🔪 Killing existing processes on port 8000: {pids}")
                for pid in pids:
                    try:
                        os.kill(pid, signal.SIGTERM)
                        # Give it a moment to terminate gracefully
                        subprocess.run(["sleep", "1"], capture_output=True)
                    except ProcessLookupError:
                        pass  # Process already gone
                    except OSError as e:
                        print(f"⚠️  Failed to kill PID {pid}: {e}")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        # lsof not available or timeout, try alternative methods
        try:
            # Try pkill as fallback
            subprocess.run(["pkill", "-f", "uvicorn.*app.main"], capture_output=True)
            subprocess.run(
                ["pkill", "-f", "python.*uvicorn.*app.main"], capture_output=True
            )
            print("🔪 Attempted to kill existing uvicorn processes with pkill")
        except FileNotFoundError:
            try:
                # Last resort: killall if available
                subprocess.run(["killall", "python"], capture_output=True)
                subprocess.run(["killall", "uvicorn"], capture_output=True)
                print("🔪 Attempted to kill with killall")
            except FileNotFoundError:
                print("⚠️  No process killing tools available, continuing anyway")

    # Give processes a moment to fully terminate
    try:
        subprocess.run(["sleep", "2"], capture_output=True)
    except FileNotFoundError:
        import time

        time.sleep(2)


def main():
    """Start the application with uvicorn"""
    project_root = Path(__file__).parent
    os.chdir(project_root)

    print("🔧 Preparing to start application...")

    # Kill any existing processes that might be using the port
    kill_existing_processes()

    # Use python -m uvicorn to ensure proper module resolution
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--reload",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
    ]

    print("🚀 Starting Alpine + FastAPI application...")
    print(f"📂 Working directory: {project_root}")
    print(f"💻 Command: {' '.join(cmd)}")
    print()
    print("🌐 Once started, visit:")
    print("   - http://localhost:8000 (main app)")
    print("   - http://localhost:8000/admin/login (admin panel)")
    print()
    print("✨ Features: Dark mode toggle, input icons, improved UI!")
    print("=" * 50)

    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n👋 Application stopped")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Failed to start application: {e}")
        print("\n💡 Make sure you have installed dependencies:")
        print("   pip install -r requirements.txt")
        sys.exit(1)


if __name__ == "__main__":
    main()
