"""
Setup script to compile Cython extensions for EDGECORE.
Much simpler than C++/pybind11/CMake approach.

Usage:
    python setup.py build_ext --inplace
"""

from setuptools import setup, find_packages, Extension
from Cython.Build import cythonize
import numpy as np

# Define Cython extensions
ext_modules = [
    Extension(
        name='models.cointegration_fast',
        sources=['models/cointegration_fast.pyx'],
        include_dirs=[np.get_include()],
        extra_compile_args=['/O2'],  # Windows MSVC optimization
        language='c',
    )
]

setup(
    name='edgecore',
    version='0.1.0',
    description='Statistical Arbitrage Trading System - Python/Cython Hybrid',
    author='EDGECORE Team',
    packages=find_packages(),
    ext_modules=cythonize(
        ext_modules,
        compiler_directives={
            'language_level': '3',
            'boundscheck': False,
            'wraparound': False,
            'cdivision': True,
            'nonecheck': False,
        }
    ),
    install_requires=[
        'numpy>=1.20',
        'pandas>=1.3',
        'Cython>=0.29',
    ],
    python_requires='>=3.9',
)
