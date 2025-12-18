# ruff: noqa: D100
"""Build configuration for Cython extensions."""

from setuptools import setup

try:
    from Cython.Build import cythonize

    ext_modules = cythonize(
        ['redux/_store_core.pyx', 'redux/_combine_reducers.pyx'],
        compiler_directives={
            'language_level': '3',
            'boundscheck': False,
            'wraparound': False,
        },
    )
except ImportError:
    ext_modules = []

setup(
    packages=['redux', 'redux_pytest'],
    ext_modules=ext_modules,
)
