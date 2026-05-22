"""Vyper CLI — Smart Contract Bug Hunter.

Installation:
    pip install -e .
    
Or for development:
    pip install -e ".[dev]"
"""

from setuptools import find_packages, setup

setup(
    name="vyper-cli",
    version="0.1.0",
    description="Smart Contract Bug Hunter — analyze, exploit, and report on Solidity contracts",
    long_description=open("README.md", encoding="utf-8").read() if __import__("os").path.exists("README.md") else "",
    long_description_content_type="text/markdown",
    author="Vyper Team",
    python_requires=">=3.10",
    packages=find_packages(include=["cli", "cli.*", "services", "services.shared", "services.shared.*"]),
    install_requires=[
        "typer>=0.12.0",
        "rich>=13.0.0",
        "httpx>=0.27.0",
        "pyyaml>=6.0",
    ],
    extras_require={
        "dev": [
            "pytest>=8.0",
            "pytest-asyncio>=0.24",
        ],
    },
    entry_points={
        "console_scripts": [
            "vyper=cli.main:entrypoint",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Topic :: Security",
        "Topic :: Software Development :: Testing",
    ],
)
