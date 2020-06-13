"""Setup file"""
from pathlib import Path
from setuptools import setup, find_packages

THIS_DIR = Path(__file__).resolve().parent


def read(path):
    return path.open().read()


REQUIRES = [
    "beancount",
    "click",
    "maya",
    "pyyaml",
    "fuzzywuzzy[speedup]",
]

EXTRAS = {"dev": ["black", "pre-commit", "flake8"]}

CLASSIFIERS = [
    "Development Status :: 3 - Alpha",
    "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
    "Natural Language :: English",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.7",
]

setup(
    # Package description.
    name="Pinto",
    description="Command line interface for manual Beancount transaction entry.",
    long_description=read(THIS_DIR / "README.md"),
    long_description_content_type="text/markdown",
    author="Sean Leavey",
    author_email="github@attackllama.com",
    url="https://github.com/SeanDS/pinto",
    # Versioning.
    use_scm_version={"write_to": "pinto/_version.py"},
    # Packages.
    packages=find_packages(),
    zip_safe=False,
    package_data={
        "finesse": ["plotting/style/*.mplstyle", "cmath/*.pxd", "simulations/*.pxd"]
    },
    # Requirements.
    python_requires=">=3.7",
    install_requires=REQUIRES,
    setup_requires=["setuptools_scm"],
    extras_require=EXTRAS,
    # Other.
    license="GPL",
    classifiers=CLASSIFIERS,
    # CLI.
    entry_points={"console_scripts": ["pinto = pinto.__main__:pinto"]},
)
