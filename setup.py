"""
Setup script for DELTA OS.

All package metadata lives in pyproject.toml [project].
This file only carries the legacy console-script entry point so both
install paths (setup.py / pyproject) register the same `delta` launcher.
"""

from setuptools import setup


setup(
    entry_points={
        "console_scripts": [
            "delta=apps.cli.delta:main",
        ],
    },
)
