"""
IndexedCP Python Server Implementation

This module provides a Python server for the IndexedCP file transfer system,
compatible with the Node.js client and Python client implementations.
"""

import os
import json
import secrets
import threading
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs


class IndexCPRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for IndexedCP uploads."""
    
    def __init__(self, server_instance, *args, **kwargs):
        self.server_instance = server_instance
        super().__init__(*args, **kwargs)
    
    def do_POST(self):
        """Handle POST requests."""
        if self.path == '/upload':
            self._handle_upload()
        else:
            self._send_404()
    
    def do_GET(self):
        """Handle GET requests."""
        self._send_404()
    
    def _handle_upload(self):
        """Handle file upload requests."""
        # Check API key authentication
        auth_header = self.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            self._send_error(401, 'Invalid or missing API key')
            return
        
        provided_api_key = auth_header[7:]  # Remove 'Bearer ' prefix
        if provided_api_key != self.server_instance.api_key:
            self._send_error(401, 'Invalid or missing API key')
            return
        
        # Get headers
        chunk_index = self.headers.get('X-Chunk-Index', '0')
        client_filename = self.headers.get('X-File-Name', 'uploaded_file.txt')
        content_length = int(self.headers.get('Content-Length', 0))
        
        try:
            # Determine actual filename to use
            if self.server_instance.filename_generator:
                actual_filename = self.server_instance.filename_generator(
                    client_filename, chunk_index, self
                )
            else:
                # Default behavior: use basename of client-provided filename
                actual_filename = os.path.basename(client_filename)
            
            # Create output file path
            output_file = os.path.join(self.server_instance.output_dir, actual_filename)
            
            # Read and write chunk data
            chunk_data = self.rfile.read(content_length)
            
            # Append chunk to file
            with open(output_file, 'ab') as f:
                f.write(chunk_data)
            
            print(f"Chunk {chunk_index} received for {client_filename} -> {actual_filename}")
            
            # Send response
            response_data = {
                'message': 'Chunk received',
                'actualFilename': actual_filename,
                'chunkIndex': int(chunk_index),
                'clientFilename': client_filename
            }
            
            self._send_json_response(200, response_data)
            
        except Exception as e:
            print(f"Upload error: {e}")
            self._send_error(500, f'Upload error: {str(e)}')
    
    def _send_json_response(self, status_code: int, data: Dict[str, Any]):
        """Send JSON response."""
        response_json = json.dumps(data).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(response_json)))
        self.end_headers()
        self.wfile.write(response_json)
    
    def _send_error(self, status_code: int, message: str):
        """Send error response."""
        error_data = {'error': message}
        self._send_json_response(status_code, error_data)
    
    def _send_404(self):
        """Send 404 Not Found response."""
        self.send_response(404)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Not Found')
    
    # def log_message(self, format, *args):
    #     """Override to suppress default logging."""
    #     pass


class IndexCPServer:
    """Python server for IndexedCP file transfer system."""
    
    def __init__(self, output_dir: Optional[str] = None, port: int = 3000, 
                 api_key: Optional[str] = None, 
                 filename_generator: Optional[Callable] = None):
        """
        Initialize the IndexedCP server.
        
        Args:
            output_dir: Directory to save uploaded files (default: current directory)
            port: Port to listen on (default: 3000)
            api_key: API key for authentication (default: auto-generated)
            filename_generator: Optional custom filename generator function
        """
        self.output_dir = output_dir or os.getcwd()
        self.port = port
        self.api_key = api_key or self.generate_api_key()
        self.filename_generator = filename_generator
        self.httpd: Optional[HTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
    
    def generate_api_key(self) -> str:
        """Generate a secure random API key."""
        return secrets.token_hex(32)
    
    def create_server(self) -> HTTPServer:
        """Create and configure the HTTP server."""
        def handler_factory(*args, **kwargs):
            return IndexCPRequestHandler(self, *args, **kwargs)
        
        self.httpd = HTTPServer(('localhost', self.port), handler_factory)
        return self.httpd
    
    def start(self, callback: Optional[Callable] = None):
        """
        Start the server in a separate thread.
        
        Args:
            callback: Optional callback function to call after server starts
        """
        if not self.httpd:
            self.create_server()
        
        def server_runner():
            try:
                print(f"Server listening on http://localhost:{self.port}")
                print(f"API Key: {self.api_key}")
                print("Include this API key in requests using the Authorization: Bearer <token> header")
                print(f"Upload endpoint: http://localhost:{self.port}/upload")
                print(f"Output directory: {self.output_dir}")
                
                if callback:
                    callback()
                
                self.httpd.serve_forever()
            except OSError as e:
                print(f"\nServer error in background thread: {e}")
                if "Address already in use" in str(e):
                    print(f"Port {self.port} is already in use. Try a different port.")
                elif "Permission denied" in str(e):
                    print(f"Permission denied on port {self.port}. Try running as administrator or use a port > 1024.")
            except Exception as e:
                print(f"\nUnexpected error in background server thread: {e}")
                print("Background server thread will terminate.")
            finally:
                # Ensure cleanup happens even if there's an error
                if hasattr(self, 'httpd') and self.httpd:
                    try:
                        self.httpd.shutdown()
                        self.httpd.server_close()
                    except:
                        pass
        
        self.server_thread = threading.Thread(target=server_runner, daemon=True)
        self.server_thread.start()
    
    def listen(self, port: Optional[int] = None, callback: Optional[Callable] = None):
        """
        Start the server (blocking call).
        
        Args:
            port: Port to listen on (overrides constructor port)
            callback: Optional callback function to call after server starts
        """
        if port:
            self.port = port
        
        if not self.httpd:
            self.create_server()
        
        print(f"Server listening on http://localhost:{self.port}")
        print(f"API Key: {self.api_key}")
        print("Include this API key in requests using the Authorization: Bearer <token> header")
        print(f"Upload endpoint: http://localhost:{self.port}/upload")
        print(f"Output directory: {self.output_dir}")
        
        if callback:
            callback()
        
        try:
            self.httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server...")
            self.close()
        except OSError as e:
            print(f"\nServer error: {e}")
            if "Address already in use" in str(e):
                print(f"Port {self.port} is already in use. Try a different port.")
            elif "Permission denied" in str(e):
                print(f"Permission denied on port {self.port}. Try running as administrator or use a port > 1024.")
            else:
                print("Check if the port is available and you have proper permissions.")
            self.close()
        except Exception as e:
            print(f"\nUnexpected server error: {e}")
            print("Server will attempt to shutdown gracefully...")
            self.close()
            raise  # Re-raise for debugging if needed
    
    def close(self):
        """Stop the server."""
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
        
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=1)


def create_simple_server(output_file: Optional[str] = None, port: int = 3000) -> HTTPServer:
    """
    Create a simple server for basic file uploads (no authentication).
    
    Args:
        output_file: File to save uploads to (default: uploaded_file.txt)
        port: Port to listen on
    
    Returns:
        HTTPServer instance
    """
    output_file = output_file or os.path.join(os.getcwd(), 'uploaded_file.txt')
    
    class SimpleHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path == '/upload':
                content_length = int(self.headers.get('Content-Length', 0))
                chunk_data = self.rfile.read(content_length)
                
                with open(output_file, 'ab') as f:
                    f.write(chunk_data)
                
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'Chunk received\n')
            else:
                self.send_response(404)
                self.end_headers()
        
        def log_message(self, format, *args):
            pass
    
    httpd = HTTPServer(('localhost', port), SimpleHandler)
    print(f"Simple server listening on http://localhost:{port}")
    print(f"Output file: {output_file}")
    
    return httpd


# Example usage and main function for testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='IndexedCP Python Server')
    parser.add_argument('--port', type=int, default=3000, help='Port to listen on')
    parser.add_argument('--output-dir', default=None, help='Output directory for uploads')
    parser.add_argument('--api-key', default=None, help='API key for authentication')
    parser.add_argument('--simple', action='store_true', help='Run simple server without authentication')
    
    args = parser.parse_args()
    
    if args.simple:
        server = create_simple_server(port=args.port)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server...")
            server.shutdown()
        except OSError as e:
            print(f"\nSimple server error: {e}")
            if "Address already in use" in str(e):
                print(f"Port {args.port} is already in use. Try a different port.")
            elif "Permission denied" in str(e):
                print(f"Permission denied on port {args.port}. Try running as administrator or use a port > 1024.")
            server.shutdown()
        except Exception as e:
            print(f"\nUnexpected error in simple server: {e}")
            server.shutdown()
            raise
    else:
        server = IndexCPServer(
            output_dir=args.output_dir,
            port=args.port,
            api_key=args.api_key
        )
        server.listen()
