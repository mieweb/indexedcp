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
    
    print("IndexedCP Server Demo")
    print("-" * 40)
    
    # Find the root directory
    script_dir = Path(__file__).parent
    python_dir = script_dir.parent
    root_dir = python_dir.parent
    
    # Configuration
    port = 3000
    api_key = "demo-key-12345"
    upload_dir = python_dir / "demo_uploads"
    server_keys_dir = root_dir / "server-keys"
    
    # Create directories
    upload_dir.mkdir(exist_ok=True)
    server_keys_dir.mkdir(exist_ok=True)
    
    print(f"Port: {port}")
    print(f"API Key: {api_key}")
    print(f"Encryption: ENABLED")
    print(f"\nServer: http://localhost:{port}")
    print(f"Endpoints: /upload, /upload-encrypted, /public-key")
    print("\nPress Ctrl+C to stop")
    print("-" * 40)
    print()
    
    # Create a simple Node.js server script
    server_script = python_dir / "temp_encrypted_server.js"
    server_script.write_text(f"""
// Temporary server script for encrypted uploads
const {{ IndexedCPServer }} = require('{root_dir}/lib/server');
const path = require('path');

const server = new IndexedCPServer({{
  port: {port},
  outputDir: '{upload_dir}',
  apiKey: '{api_key}',
  pathMode: 'sanitize',
  encryption: true,  // ENABLE ENCRYPTION
  keystoreType: 'filesystem',
  keystoreOptions: {{
    directory: '{server_keys_dir}'
  }}
}});

server.listen({port});

// Graceful shutdown
process.on('SIGINT', () => {{
  console.log('\\nShutting down server...');
  server.close();
  process.exit(0);
}});

process.on('SIGTERM', () => {{
  console.log('\\nShutting down server...');
  server.close();
  process.exit(0);
}});
""")
    
    # Start Node.js server
    try:
        process = subprocess.Popen(
            ["node", str(server_script)],
            stdout=sys.stdout,
            stderr=sys.stderr,
            cwd=str(root_dir)
        )
        
        # Wait for process to complete or be interrupted
        process.wait()
        
    except KeyboardInterrupt:
        print("\nStopping server...")
        
        # Send SIGTERM to gracefully stop the server
        if process:
            process.send_signal(signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        
        # Cleanup temporary script
        if server_script.exists():
            server_script.unlink()
        
        print("Server stopped")
        sys.exit(0)
        
    except FileNotFoundError:
        print("\nERROR: Node.js not found!")
        print("Install: brew install node (macOS) or download from nodejs.org")
        
        # Cleanup temporary script
        if server_script.exists():
            server_script.unlink()
        
        sys.exit(1)
        
    except Exception as e:
        print(f"\nERROR starting server: {e}")
        
        # Cleanup temporary script
        if server_script.exists():
            server_script.unlink()
        
        sys.exit(1)


if __name__ == "__main__":
    main()
