<<<<<<< HEAD
﻿"""
=======
"""
>>>>>>> origin/main
Setup script to compile Cython extensions for EDGECORE.
Much simpler than C++/pybind11/CMake approach.

Usage:
    python setup.py build_ext --inplace
"""

<<<<<<< HEAD
import sys

import numpy as np
from Cython.Build import cythonize
from setuptools import Extension, find_packages, setup

# Platform-appropriate optimization flag
_extra_compile_args = ['/O2'] if sys.platform == 'win32' else ['-O2']
=======
from setuptools import setup, find_packages, Extension
from Cython.Build import cythonize
import numpy as np
>>>>>>> origin/main

# Define Cython extensions
ext_modules = [
    Extension(
        name='models.cointegration_fast',
        sources=['models/cointegration_fast.pyx'],
        include_dirs=[np.get_include()],
<<<<<<< HEAD
        extra_compile_args=_extra_compile_args,
=======
        extra_compile_args=['/O2'],  # Windows MSVC optimization
>>>>>>> origin/main
        language='c',
    )
]

setup(
    name='edgecore',
<<<<<<< HEAD
    version='1.0.0',
=======
    version='0.1.0',
>>>>>>> origin/main
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
<<<<<<< HEAD
        'Cython>=3.0,<4.0',
=======
        'Cython>=0.29',
>>>>>>> origin/main
    ],
    python_requires='>=3.9',
)
