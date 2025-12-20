# ruff: noqa: T201
"""Setup script for building the binary extension of python-redux."""

import os
import sys
from pathlib import Path

from setuptools import Extension, find_packages, setup

# Add root to path to import version
root = Path(__file__).parent
sys.path.insert(0, str(root))

try:
    from version import get_version

    version = get_version()
except ImportError:
    # If version.py or dependencies fail, fallback or fail.
    # In CI, dependencies should be installed.
    print('Warning: Could not import get_version from version.py')
    version = '0.0.0.dev0'


def get_extensions() -> list[Extension]:
    """Dynamically find all C extensions in the redux/ directory."""
    extensions: list[Extension] = []
    # Find all .c files in redux/
    for path in (root / 'redux').rglob('*.c'):
        # Construct module name: redux/store.c -> redux.store
        # relatives_to root
        rel_path = path.relative_to(root)
        module_name = str(rel_path.with_suffix('')).replace(os.sep, '.')

        extensions.append(Extension(module_name, [str(rel_path)]))
    return extensions


setup(
    name='python-redux',
    version=version,
    description='Redux implementation for Python (Binary Extension)',
    packages=find_packages(include=['redux', 'redux.*']),
    ext_modules=get_extensions(),
    include_package_data=True,
    # Add other metadata as needed matching pyproject.toml
    author='Sassan Haradji',
    author_email='me@sassanh.com',
    url='https://github.com/sassanh/python-redux/',
)
