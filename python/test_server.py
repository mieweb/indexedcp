#!/usr/bin/env python3
"""
IndexedCP Python Server Tests

Test suite for the IndexedCP Python server implementation.
"""

import os
import sys
import time
import json
import threading
import requests
import tempfile
import unittest
from pathlib import Path

# Add the parent directory to path for importing indexedcp
sys.path.insert(0, str(Path(__file__).parent))

from indexedcp import IndexCPServer, create_simple_server


class TestIndexCPServer(unittest.TestCase):
    """Test cases for IndexedCP server."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.server = None
        self.server_thread = None
        
    def tearDown(self):
        """Clean up after tests."""
        if self.server:
            self.server.close()
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=1)
        
        # Clean up test files
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def start_server(self, port=3004, api_key="test-key"):
        """Start server in background thread."""
        self.server = IndexCPServer(
            output_dir=self.test_dir,
            port=port,
            api_key=api_key
        )
        
        def server_runner():
            self.server.listen()
        
        self.server_thread = threading.Thread(target=server_runner, daemon=True)
        self.server_thread.start()
        time.sleep(0.5)  # Wait for server to start
    
    def test_server_creation(self):
        """Test server creation and basic properties."""
        server = IndexCPServer(
            output_dir=self.test_dir,
            port=3005,
            api_key="test-api-key"
        )
        
        self.assertEqual(server.output_dir, self.test_dir)
        self.assertEqual(server.port, 3005)
        self.assertEqual(server.api_key, "test-api-key")
        self.assertIsNone(server.filename_generator)
    
    def test_api_key_generation(self):
        """Test automatic API key generation."""
        server = IndexCPServer()
        self.assertIsNotNone(server.api_key)
        self.assertEqual(len(server.api_key), 64)  # 32 bytes * 2 (hex)
    
    def test_upload_with_valid_api_key(self):
        """Test file upload with valid API key."""
        self.start_server(port=3006, api_key="valid-key")
        
        # Test data
        test_data = b"Hello, IndexedCP!"
        headers = {
            'Authorization': 'Bearer valid-key',
            'X-Chunk-Index': '0',
            'X-File-Name': 'test.txt',
            'Content-Type': 'application/octet-stream'
        }
        
        # Upload chunk
        response = requests.post(
            'http://localhost:3006/upload',
            data=test_data,
            headers=headers
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check response
        response_data = response.json()
        self.assertEqual(response_data['message'], 'Chunk received')
        self.assertEqual(response_data['actualFilename'], 'test.txt')
        self.assertEqual(response_data['chunkIndex'], 0)
        self.assertEqual(response_data['clientFilename'], 'test.txt')
        
        # Check file was created
        output_file = os.path.join(self.test_dir, 'test.txt')
        self.assertTrue(os.path.exists(output_file))
        
        with open(output_file, 'rb') as f:
            self.assertEqual(f.read(), test_data)
    
    def test_upload_with_invalid_api_key(self):
        """Test file upload with invalid API key."""
        self.start_server(port=3007, api_key="valid-key")
        
        test_data = b"This should be rejected"
        headers = {
            'Authorization': 'Bearer invalid-key',
            'X-Chunk-Index': '0',
            'X-File-Name': 'test.txt'
        }
        
        response = requests.post(
            'http://localhost:3007/upload',
            data=test_data,
            headers=headers
        )
        
        self.assertEqual(response.status_code, 401)
        response_data = response.json()
        self.assertIn('error', response_data)
    
    def test_upload_without_api_key(self):
        """Test file upload without API key."""
        self.start_server(port=3008, api_key="valid-key")
        
        test_data = b"This should also be rejected"
        
        response = requests.post(
            'http://localhost:3008/upload',
            data=test_data
        )
        
        self.assertEqual(response.status_code, 401)
    
    def test_multiple_chunks(self):
        """Test uploading multiple chunks to same file."""
        self.start_server(port=3009, api_key="test-key")
        
        headers_base = {
            'Authorization': 'Bearer test-key',
            'X-File-Name': 'multipart.txt'
        }
        
        # Upload first chunk
        headers1 = {**headers_base, 'X-Chunk-Index': '0'}
        response1 = requests.post(
            'http://localhost:3009/upload',
            data=b"First chunk",
            headers=headers1
        )
        self.assertEqual(response1.status_code, 200)
        
        # Upload second chunk
        headers2 = {**headers_base, 'X-Chunk-Index': '1'}
        response2 = requests.post(
            'http://localhost:3009/upload',
            data=b" Second chunk",
            headers=headers2
        )
        self.assertEqual(response2.status_code, 200)
        
        # Check combined file
        output_file = os.path.join(self.test_dir, 'multipart.txt')
        with open(output_file, 'rb') as f:
            content = f.read()
            self.assertEqual(content, b"First chunk Second chunk")
    
    def test_custom_filename_generator(self):
        """Test server with custom filename generator."""
        def custom_generator(client_filename, chunk_index, request_handler):
            return f"custom_{os.path.basename(client_filename)}"
        
        server = IndexCPServer(
            output_dir=self.test_dir,
            port=3010,
            api_key="test-key",
            filename_generator=custom_generator
        )
        
        self.server = server
        
        def server_runner():
            server.listen()
        
        self.server_thread = threading.Thread(target=server_runner, daemon=True)
        self.server_thread.start()
        time.sleep(0.5)
        
        # Upload file
        headers = {
            'Authorization': 'Bearer test-key',
            'X-Chunk-Index': '0',
            'X-File-Name': 'original.txt'
        }
        
        response = requests.post(
            'http://localhost:3010/upload',
            data=b"Test content",
            headers=headers
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(response_data['actualFilename'], 'custom_original.txt')
        
        # Check file exists with custom name
        custom_file = os.path.join(self.test_dir, 'custom_original.txt')
        self.assertTrue(os.path.exists(custom_file))
    
    def test_404_for_invalid_endpoints(self):
        """Test 404 response for invalid endpoints."""
        self.start_server(port=3011, api_key="test-key")
        
        # Test GET request to upload endpoint
        response = requests.get('http://localhost:3011/upload')
        self.assertEqual(response.status_code, 404)
        
        # Test POST to invalid endpoint
        response = requests.post('http://localhost:3011/invalid')
        self.assertEqual(response.status_code, 404)


class TestSimpleServer(unittest.TestCase):
    """Test cases for simple server."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.output_file = os.path.join(self.test_dir, 'simple_output.txt')
        
    def tearDown(self):
        """Clean up after tests."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_simple_server_upload(self):
        """Test simple server upload functionality."""
        # Start simple server in background
        server = create_simple_server(output_file=self.output_file, port=3012)
        
        def server_runner():
            server.serve_forever()
        
        server_thread = threading.Thread(target=server_runner, daemon=True)
        server_thread.start()
        time.sleep(0.5)
        
        try:
            # Upload data
            test_data = b"Simple server test data"
            response = requests.post(
                'http://localhost:3012/upload',
                data=test_data
            )
            
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.text, 'Chunk received\n')
            
            # Check file content
            with open(self.output_file, 'rb') as f:
                self.assertEqual(f.read(), test_data)
                
        finally:
            server.shutdown()
            server.server_close()


def run_tests():
    """Run all tests."""
    unittest.main(verbosity=2)


if __name__ == "__main__":
    run_tests()
