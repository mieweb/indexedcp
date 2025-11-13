#!/usr/bin/env python3
"""
IndexedCP Server Demo

This script demonstrates running an IndexedCP server that accepts
file uploads from clients.

Features:
- Chunked file upload support
- API key authentication
- Multiple path handling modes
- Real-time logging of incoming requests
"""

import uvicorn
from indexedcp.server import IndexedCPServer
import sys


def main():
    """Run IndexedCP demo server with detailed logging."""
    
    print("=" * 70)
    print(" IndexedCP Server Demo")
    print("=" * 70)
    print()
    
    # Server configuration
    upload_dir = "./demo_uploads"
    api_key = "demo-key-12345"
    port = 3000
    
    print(" Server Configuration:")
    print(f"   • Upload Directory: {upload_dir}")
    print(f"   • API Key: {api_key}")
    print(f"   • Port: {port}")
    print(f"   • Path Mode: ignore (generates unique filenames)")
    print()
    
    # Create server instance
    server = IndexedCPServer(
        upload_dir=upload_dir,
        port=port,
        api_keys=[api_key],
        path_mode="ignore",
        log_level="INFO"
    )
    
    print(" Server initialized successfully!")
    print()
    print("=" * 70)
    print(" Server Starting")
    print("=" * 70)
    print(f"   URL: http://localhost:{port}")
    print(f"   Upload Endpoint: http://localhost:{port}/upload")
    print(f"   Health Check: http://localhost:{port}/health")
    print()
    print("Server is now ready to accept file uploads from clients")
    print("Watch this terminal for real-time upload logs")
    print()
    print("Press Ctrl+C to stop the server")
    print("=" * 70)
    print()
    
    # Create and run FastAPI app
    app = server.create_app()
    
    try:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=port,
            log_level="info",
            access_log=True
        )
    except KeyboardInterrupt:
        print()
        print("=" * 70)
        print(" Server stopped by user")
        print("=" * 70)
        sys.exit(0)


if __name__ == "__main__":
    main()