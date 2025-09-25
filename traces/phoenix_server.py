#!/usr/bin/env python3
"""
Phoenix server startup script for PMS Assistant
This script initializes and starts the Phoenix evaluation server.
"""

import os
import sys
import asyncio
import subprocess
import time
from pathlib import Path
import json
from typing import Optional, Dict, Any, List

# Local imports
from config import PHOENIX_CONFIG, PHOENIX_DB_CONFIG, PHOENIX_SERVER_CONFIG


class PhoenixServerManager:
    """Manages the Phoenix server lifecycle"""

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.host = PHOENIX_CONFIG["host"]
        self.port = PHOENIX_CONFIG["port"]

    def is_server_running(self) -> bool:
        """Check if Phoenix server is already running"""
        try:
            import requests
            response = requests.get(f"http://{self.host}:{self.port}/health", timeout=2)
            return response.status_code == 200
        except:
            return False

    def start_server(self) -> bool:
        """Start the Phoenix server"""
        if self.is_server_running():
            print(f"✅ Phoenix server is already running on {self.host}:{self.port}")
            return True

        try:
            print(f"🚀 Starting Phoenix server on {self.host}:{self.port}...")

            # Set environment variables for Phoenix
            env = os.environ.copy()
            env.update({
                "PHOENIX_HOST": self.host,
                "PHOENIX_PORT": str(self.port),
                "PHOENIX_LOG_LEVEL": PHOENIX_CONFIG["log_level"]
            })

            # Start Phoenix server in background
            self.process = subprocess.Popen(
                [sys.executable, "-m", "phoenix.server.main", "serve"],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=os.getcwd()
            )

            # Wait a moment for server to start
            time.sleep(3)

            if self.is_server_running():
                print(f"✅ Phoenix server started successfully!")
                print(f"🌐 Dashboard available at: http://{self.host}:{self.port}")
                return True
            else:
                print("❌ Failed to start Phoenix server")
                return False

        except Exception as e:
            print(f"❌ Error starting Phoenix server: {e}")
            return False

    def stop_server(self):
        """Stop the Phoenix server"""
        if self.process and self.process.poll() is None:
            print("🛑 Stopping Phoenix server...")
            self.process.terminate()
            self.process.wait()
            print("✅ Phoenix server stopped")
        else:
            print("ℹ️  Phoenix server is not running")

    def get_server_logs(self) -> str:
        """Get server logs"""
        if self.process:
            stdout, stderr = self.process.communicate()
            return f"STDOUT: {stdout.decode()}\nSTDERR: {stderr.decode()}"
        return "No server process"


async def main():
    """Main function to start Phoenix server"""
    print("🔧 Starting Phoenix evaluation server for PMS Assistant...")
    print("=" * 60)

    # Initialize Phoenix server manager
    server_manager = PhoenixServerManager()

    # Start Phoenix server
    if not server_manager.start_server():
        print("❌ Could not start Phoenix server. Exiting.")
        return

    print("\n" + "=" * 60)
    print("🎯 Phoenix Server Started Successfully!")
    print("=" * 60)
    print(f"🌐 Phoenix Dashboard: http://{server_manager.host}:{server_manager.port}")
    print("📊 Ready for evaluation data and traces")

    # Instructions
    print("\n📋 Next Steps:")
    print("1. Open your browser and go to the Phoenix dashboard")
    print("2. Run evaluation: python setup.py")
    print("3. View traces and performance metrics in real-time")
    print("4. Upload evaluation datasets for analysis")

    print("\n🛑 To stop Phoenix server later, run:")
    print("   python phoenix.py --stop")

    # Keep server running if requested
    keep_running = input("\nKeep Phoenix server running? (y/n): ").lower().strip()

    if keep_running != 'y':
        print("🛑 Stopping Phoenix server...")
        server_manager.stop_server()

    print("✅ Phoenix server stopped!")


def stop_server():
    """Stop the Phoenix server"""
    manager = PhoenixServerManager()
    manager.stop_server()
    print("✅ Phoenix server stopped")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--stop":
        stop_server()
    else:
        asyncio.run(main())
