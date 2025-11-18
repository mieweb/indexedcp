#!/usr/bin/env python3
"""
IndexedCP Server Demo

This script starts the Node.js server for testing.
Run this in one terminal, then run client_demo.py in another terminal.
"""

import os
import sys
import subprocess
import signal
from pathlib import Path


def main():
    """Start the Node.js IndexedCP server."""
    
    print("=" * 70)
    print(" IndexedCP Server Demo (Node.js)")
    print("=" * 70)
    print()
    
    # Find the indexcp CLI in parent directory
    script_dir = Path(__file__).parent
    python_dir = script_dir.parent
    root_dir = python_dir.parent
    indexcp_cli = root_dir / "bin" / "indexcp"
    
    if not indexcp_cli.exists():
        print("ERROR: indexcp CLI not found at:", indexcp_cli)
        print()
        print("Expected location: ../bin/indexcp")
        print("Please ensure you're running from the correct directory.")
        sys.exit(1)
    
    # Configuration
    port = 3000
    api_key = "demo-key-12345"
    upload_dir = python_dir / "demo_uploads"
    path_mode = "sanitize"  # Use sanitize mode for proper chunked upload support
    
    # Create upload directory
    upload_dir.mkdir(exist_ok=True)
    
    print("Configuration:")
    print(f"   • CLI: {indexcp_cli}")
    print(f"   • Port: {port}")
    print(f"   • API Key: {api_key}")
    print(f"   • Upload Directory: {upload_dir}")
    print(f"   • Path Mode: {path_mode} (preserves filenames with session tracking)")
    print()
    print("=" * 70)
    print(" Starting Node.js Server")
    print("=" * 70)
    print()
    print(f"Server will listen on: http://localhost:{port}")
    print(f"Upload endpoint: http://localhost:{port}/upload")
    print()
    print("Press Ctrl+C to stop the server")
    print("=" * 70)
    print()
    
    # Start Node.js server using indexcp CLI
    try:
        # Set API key via environment variable (recommended approach)
        env = os.environ.copy()
        env["INDEXEDCP_API_KEY"] = api_key
        
        # Run: indexcp server 3000 ./python/demo_uploads --path-mode ignore
        process = subprocess.Popen(
            [
                str(indexcp_cli),
                "server",
                str(port),
                str(upload_dir),
                "--path-mode", path_mode
            ],
            env=env,
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        
        # Wait for process to complete or be interrupted
        process.wait()
        
    except KeyboardInterrupt:
        print()
        print("=" * 70)
        print(" Stopping server...")
        print("=" * 70)
        
        # Send SIGTERM to gracefully stop the server
        if process:
            process.send_signal(signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        
        print("Server stopped")
        sys.exit(0)
        
    except FileNotFoundError:
        print()
        print("ERROR: Node.js not found!")
        print()
        print("Please install Node.js:")
        print("  • macOS: brew install node")
        print("  • Ubuntu: sudo apt-get install nodejs")
        print("  • Windows: Download from https://nodejs.org/")
        print()
        sys.exit(1)
        
    except Exception as e:
        print()
        print(f"ERROR starting server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
