# Tests

This directory contains all test suites for IndexedCP.

## Test Files

### `test-all.js`
Master test runner that executes all test suites sequentially.

**Usage:**
```bash
npm test
```

### `test-all-examples.js`
Comprehensive functional tests covering:
- Basic file uploads
- Multiple file transfers
- Large file chunking (5MB+)
- Filename mapping
- API key authentication
- Error handling
- Resume capabilities

**Usage:**
```bash
npm run test:functional
```

**Tests:** 7

### `security-test.js`
Security validation tests covering:
- Path traversal attempts
- Absolute path blocking
- Subdirectory blocking
- Invalid filename patterns
- Filesystem isolation
- Directory boundary checks

**Usage:**
```bash
npm run test:security
```

**Tests:** 18

### `test-path-modes.js`
Path handling mode tests covering:
- Sanitize mode (default) - path stripping and overwrite prevention
- Allow-paths mode - subdirectory support with security
- Ignore mode - unique filename generation
- Security validation for each mode

**Usage:**
```bash
npm run test:path-modes
```

**Tests:** 9

## Running Tests

### All Tests
```bash
npm test
```

This runs functional and security test suites (path mode tests run separately).

### Individual Test Suites
```bash
# Functional tests only
npm run test:functional

# Security tests only
npm run test:security

# Path mode tests only
npm run test:path-modes
```

## Test Results

All tests must pass before:
- Merging pull requests
- Creating releases
- Deploying to production

Expected output:
```
══════════════════════════════════════════════════════════════════════
Complete Test Summary
══════════════════════════════════════════════════════════════════════
Functional Tests                         ✓ PASS
Security Tests                           ✓ PASS

Total Test Suites: 2
Passed: 2
Failed: 0
══════════════════════════════════════════════════════════════════════
All tests passed! 🎉
```

## Test Coverage

| Test Suite | Tests | Description |
|------------|-------|-------------|
| Functional | 7 | Core upload/download functionality |
| Security | 18 | Attack prevention & validation |
| Path Modes | 9 | Path handling mode validation |
| **Total** | **34** | **Complete coverage** |

## Adding New Tests

To add a new test to an existing suite:

1. Open the appropriate test file (`test-all-examples.js` or `security-test.js`)
2. Add your test function following the existing pattern
3. Add the test to the `tests` array
4. Run `npm test` to verify

To create a new test suite:

1. Create a new test file in this directory
2. Update `test-all.js` to include your new suite
3. Add a new script to `package.json` if needed
4. Update this README

## CI/CD Integration

These tests are designed to run in CI/CD pipelines:

```yaml
# GitHub Actions example
- run: npm test
```

Exit codes:
- `0` = All tests passed
- `1` = One or more tests failed

## Troubleshooting

### Port Conflicts
Tests use ports 3000 (functional) and 3335 (security).

```bash
# Check what's using the ports
lsof -i :3000
lsof -i :3335
```

### Module Not Found
Make sure you're running tests from the project root:

```bash
cd /path/to/IndexedCP
npm test
```

### Clean State
To ensure a clean test environment:

```bash
# Remove test artifacts
rm -rf test-uploads test-security-uploads ~/.indexcp/db

# Run tests
npm test
```

## Documentation

For more details, see:
- [../TESTING.md](../TESTING.md) - Complete testing guide
- [../SECURITY.md](../SECURITY.md) - Security documentation
- [../TEST-SUITE.md](../TEST-SUITE.md) - Original test suite docs
