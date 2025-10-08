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
    """Phoenix disabled: no-op starter."""
    print("Phoenix server start requested, but Phoenix is disabled.")
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
    print("\n2️⃣  Phoenix is disabled; skipping server start.")


if __name__ == "__main__":
    main()