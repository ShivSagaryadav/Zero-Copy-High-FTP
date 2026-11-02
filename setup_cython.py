"""Build the optional Cython matching extension in-place."""
from __future__ import annotations

from setuptools import Extension, setup

try:
    from Cython.Build import cythonize
except ImportError as exc:
    raise SystemExit(
        "Install the optional build dependency first: "
        "python -m pip install -r requirements-cython.txt"
    ) from exc


setup(
    name="chronosmatch-cython",
    ext_modules=cythonize(
        [
            Extension(
                "chronosmatch._cython_matcher",
                ["chronosmatch/_cython_matcher.pyx"],
            )
        ],
        build_dir="build/cython",
        compiler_directives={"language_level": 3},
    ),
)
