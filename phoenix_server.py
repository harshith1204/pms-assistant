#!/usr/bin/env python3
"""
Simple Phoenix Server Restart Script
Kills any existing Phoenix processes and starts a fresh one.
"""

import os
import sys
import time
import signal
import subprocess


def find_and_kill_phoenix():
    """Find and kill all Phoenix processes"""
    try:
        # Use pgrep to find Phoenix processes
        result = subprocess.run(['pgrep', '-f', 'phoenix'],
                              capture_output=True, text=True)

        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            print(f"Found {len(pids)} Phoenix process(es): {pids}")

            for pid in pids:
                try:
                    pid = int(pid.strip())
                    print(f"Stopping Phoenix process {pid}...")
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(1)

                    # Check if still running
                    try:
                        os.kill(pid, 0)
                        print(f"Process {pid} still running, using SIGKILL...")
                        os.kill(pid, signal.SIGKILL)
                    except OSError:
                        print(f"Process {pid} stopped successfully")

                except (ValueError, ProcessLookupError):
                    continue

            print("All Phoenix processes stopped")
        else:
            print("No Phoenix processes found")

    except FileNotFoundError:
        print("pgrep not available, trying alternative method...")

        # Alternative method using ps
        try:
            result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
            phoenix_processes = []

            for line in result.stdout.split('\n'):
                if 'phoenix' in line.lower() and 'python' in line:
                    parts = line.split()
                    if len(parts) > 1:
                        try:
                            pid = int(parts[1])
                            phoenix_processes.append(pid)
                        except ValueError:
                            continue

            if phoenix_processes:
                print(f"Found Phoenix processes: {phoenix_processes}")
                for pid in phoenix_processes:
                    try:
                        print(f"Stopping Phoenix process {pid}...")
                        os.kill(pid, signal.SIGTERM)
                        time.sleep(1)

                        try:
                            os.kill(pid, 0)
                            os.kill(pid, signal.SIGKILL)
                        except OSError:
                            pass

                    except ProcessLookupError:
                        pass
                print("All Phoenix processes stopped")
            else:
                print("No Phoenix processes found")

        except Exception as e:
            print(f"Error finding processes: {e}")


def start_phoenix_server():
    """Start Phoenix server"""
    try:
        print("Starting Phoenix server...")

        # Set environment variables
        env = os.environ.copy()
        env.update({
            'PHOENIX_HOST': 'localhost',
            'PHOENIX_PORT': '6006',
            'PHOENIX_LOG_LEVEL': 'INFO'
        })

        # Start Phoenix server
        process = subprocess.Popen(
            [sys.executable, '-m', 'phoenix.server.main', 'serve'],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        print(f"Phoenix server started with PID: {process.pid}")
        print("Phoenix dashboard: http://localhost:6006")

        # Wait a moment for server to initialize
        time.sleep(3)

        # Check if process is still running
        if process.poll() is None:
            print("✅ Phoenix server started successfully!")
            return True
        else:
            print("❌ Phoenix server failed to start")
            # Get the error output
            stdout, stderr = process.communicate()
            if stderr:
                print(f"Error output: {stderr.decode()}")
            if stdout:
                print(f"Output: {stdout.decode()}")
            return False

    except Exception as e:
        print(f"Error starting Phoenix server: {e}")
        return False


def main():
    """Main function"""
    print("🔄 Restarting Phoenix server...")

    # Kill existing processes
    print("\n1️⃣  Stopping existing Phoenix processes...")
    find_and_kill_phoenix()

    # Small delay to ensure processes are fully stopped
    time.sleep(2)

    # Start new server
    print("\n2️⃣  Starting fresh Phoenix server...")
    if start_phoenix_server():
        print("\n🎉 Phoenix server restarted successfully!")
        print("Ready to use at http://localhost:6006")
    else:
        print("\n❌ Failed to start Phoenix server")
        sys.exit(1)


if __name__ == "__main__":
    main()