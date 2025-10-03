"""
Setup script for IndexedCP Python client.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
this_directory = Path(__file__).parent
long_description = (this_directory / "../README.md").read_text() if (this_directory / "../README.md").exists() else ""

setup(
    name="indexedcp",
    version="1.0.0",
    description="Python client and server for IndexedCP secure, efficient, and resumable file transfer",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="adithyasn7@gmail.com",
    python_requires=">=3.7",
    packages=find_packages(),
    install_requires=[
        "requests>=2.25.0",
    ],
    scripts=["bin/indexcp", "bin/indexcp-server"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Networking",
    ],
    keywords="file-transfer upload resumable chunks streaming",
    project_urls={
        "Source": "https://github.com/mieweb/IndexedCP",
        "Bug Reports": "https://github.com/mieweb/IndexedCP/issues",
    },
)