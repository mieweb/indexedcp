#!/usr/bin/env python3
"""
IndexedCP Demo Server
Simple server for demonstration purposes
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from indexedcp import IndexCPServer


def main():
    """Start the demo server."""
    print("=" * 60)
    print("IndexedCP Demo Server")
    print("=" * 60)
    
    # Generate API key
    api_key = "demo-key-2024"
    
    print(f"\n📋 Server Configuration:")
    print(f"   Port: 3000")
    print(f"   API Key: {api_key}")
    print(f"   Output Directory: ./uploads")
    print(f"\n🔑 To upload files, use this API key in the client")
    print(f"   Export it: export INDEXCP_API_KEY={api_key}")
    print("=" * 60)
    
    # Create server
    server = IndexCPServer(
        output_dir="./uploads",
        port=3000,
        api_key=api_key
    )
    
    def on_ready():
        print("\n✅ Server is running and ready to receive files!")
        print("   Endpoint: http://localhost:3000/upload")
        print("\n📝 Press Ctrl+C to stop the server")
        print("=" * 60)
    
    try:
        server.listen(callback=on_ready)
    except KeyboardInterrupt:
        print("\n\n🛑 Server stopped by user")
        print("=" * 60)


if __name__ == "__main__":
    main()
