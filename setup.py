"""Vyper backend library — Smart Contract Bug Hunter services.

This package contains the shared library used by all microservices.

Installation:
    pip install -e .
    
Or for development:
    pip install -e ".[dev]"
"""

from setuptools import find_packages, setup

setup(
    name="vyper-lib",
    version="0.2.0",
    description="Vyper backend library — services for Smart Contract Bug Hunter",
    long_description=open("README.md", encoding="utf-8").read() if __import__("os").path.exists("README.md") else "",
    long_description_content_type="text/markdown",
    author="Vyper Team",
    python_requires=">=3.10",
    packages=find_packages(include=["services", "services.*"]),
    install_requires=[
        "httpx>=0.27.0",
        "pyyaml>=6.0",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Topic :: Security",
        "Topic :: Software Development :: Testing",
    ],
)
