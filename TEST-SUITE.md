# IndexedCP Test Suite

## Overview

This comprehensive test suite validates all major functionality of the IndexedCP library by running a local server and testing various file transfer scenarios.

## Running the Tests

```bash
npm test
```

## Test Coverage

The test suite includes the following tests:

### 1. **Basic Client Upload**
- Tests simple file upload from client to server
- Validates that `myfile.txt` is correctly transferred
- Verifies file content integrity after upload

### 2. **Filename Mapping**
- Tests filename preservation from client to server
- Validates that the server returns the correct filename mapping
- Ensures file is saved with the expected name

### 3. **Multiple Files Upload**
- Tests uploading multiple files in a single session
- Creates 3 test files and uploads them all
- Verifies each file is correctly received and saved
- Tests batch upload functionality

### 4. **Large File Upload (Chunking)**
- Tests chunking mechanism with a 5MB file
- Validates that large files are split into 1MB chunks
- Verifies reassembly of chunks on the server
- Confirms file size and content integrity

### 5. **Error Handling - Missing API Key**
- Tests authentication requirement
- Validates that uploads without API key are rejected
- Ensures proper error messages are returned

### 6. **Error Handling - Wrong API Key**
- Tests authentication validation
- Validates that incorrect API keys are rejected
- Ensures security through authentication enforcement

### 7. **Resume Upload Capability**
- Tests the resumable upload feature
- Validates IndexedDB buffering mechanism
- Ensures files can be buffered and uploaded reliably

## Test Configuration

- **Server Port**: 3000
- **Upload Directory**: `./test-uploads` (cleaned up after tests)
- **Test API Key**: `test-api-key-12345`
- **Default Chunk Size**: 1MB
- **Large File Size**: 5MB

## Test Output

The test suite provides colored, formatted output:
- ✓ Green checkmarks for passed tests
- ✗ Red X marks for failed tests
- ℹ Blue info messages for progress updates
- Clear test summaries with pass/fail counts

## What Gets Tested

### Client Features
- File buffering with IndexedDB
- Chunked file uploads
- API key authentication
- Multiple file handling
- Error handling and recovery

### Server Features
- HTTP file reception
- Chunk reassembly
- API key validation
- File saving with original filenames
- Multiple concurrent uploads

### Integration
- Client-server communication
- File transfer integrity
- Authentication flow
- Error propagation

## Requirements

- Node.js >= 18.0.0
- All dependencies installed (`npm install`)
- Write permissions for test directory

## Clean Up

The test suite automatically:
- Creates a temporary `test-uploads` directory
- Cleans up test files after each test
- Removes the uploads directory after completion
- Closes the server gracefully

## Exit Codes

- `0`: All tests passed
- `1`: One or more tests failed

## Adding New Tests

To add a new test:

1. Create a test function following the pattern:
```javascript
async function testNewFeature(server) {
  logTest('Test Name');
  // Test implementation
  logSuccess('Test passed message');
}
```

2. Add it to the `tests` array in `runAllTests()`:
```javascript
const tests = [
  // ... existing tests
  { name: 'New Feature', fn: testNewFeature }
];
```

## Continuous Integration

This test suite is designed to be CI/CD friendly:
- No interactive prompts during normal execution
- Clear exit codes
- Self-contained with automatic cleanup
- Deterministic results
