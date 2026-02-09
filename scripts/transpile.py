# ruff: noqa: T201
"""Transpile all python files in redux/ to C files using Cython."""

from pathlib import Path

from Cython.Build import cythonize


def transpile() -> None:
    """Found all python files in redux/ and transpile them to C files using Cython."""
    root = Path(__file__).parent.parent
    redux_dir = root / 'redux'
    redux_pytest_dir = root / 'redux_pytest'

    # Find all .py files
    py_files = [*redux_dir.rglob('*.py'), *redux_pytest_dir.rglob('*.py')]

    source_files = []

    print(f'Found {len(py_files)} Python files to transpile.')

    for py_file in py_files:
        # Skip _version.py as it is often generated/problematic
        if py_file.name == '_version.py':
            continue

        source_files.append(str(py_file))

    # Cythonize in place to produce .c files next to .py files
    # We use language_level=3 for Python 3
    # keep_path=True is implied by passing full paths often, but good to ensure
    # directory structure is respected in modules if we were building them.
    # Here we just generate sources.
    cythonize(source_files, language_level='3', force=True)
    print('Transpilation complete.')


if __name__ == '__main__':
    transpile()
