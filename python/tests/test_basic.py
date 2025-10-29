"""
Basic test to verify pytest configuration
"""
import pytest


def test_package_import():
    """Test that the package can be imported"""
    import indexedcp
    assert indexedcp.__version__ == "0.1.0"


def test_basic_assertion():
    """Test that pytest is working correctly"""
    assert True


@pytest.mark.asyncio
async def test_async_support():
    """Test that async tests work"""
    assert True
