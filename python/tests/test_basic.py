"""
Basic test to verify pytest configuration
"""
import pytest


def test_package_import():
    """Test that the package can be imported"""
    import indexedcp
    assert indexedcp.__version__ == "0.1.0"
