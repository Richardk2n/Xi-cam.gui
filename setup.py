"""
Usage: pip install -e .
       python setup.py install
       python setup.py bdist_wheel
       python setup.py sdist bdist_egg
       twine upload dist/*
"""

from codecs import open
from os import path

from setuptools import setup
import versioneer

# Set the long_description from the README
here = path.abspath(path.dirname(__file__))
with open(path.join(here, "README.rst"), encoding="utf-8") as f:
    long_description = f.read()

import os

if "APPVEYOR" in os.environ and os.environ["APPVEYOR"]:
    pyqt = ["PyQt5"]
else:
    pyqt = []

setup(
    name="xicam.gui",
    # Versions should comply with PEP440.  For a discussion on single-sourcing
    # the version across setup.py and the project code, see
    # https://packaging.python.org/en/latest/single_source_version.html
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    description="The CAMERA platform for synchrotron data management, visualization, and reduction. The xicam.gui "
    "package contains all gui code of the Xi-cam platform, as part of the xicam namespace package. For the "
    'backend components, see "xicam.core".',
    long_description=long_description,
    # The project's main homepage.
    url="https://github.com/ronpandolfi/Xi-cam",
    # Author details
    author="Ronald J Pandolfi",
    author_email="ronpandolfi@lbl.gov",
    # Choose your license
    license="BSD",
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        "Development Status :: 3 - Alpha",
        # Indicate who your project is intended for
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Physics",
        # Pick your license as you wish (should match "license" above)
        "License :: OSI Approved :: BSD License",
        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        "Programming Language :: Python :: 3.6",
    ],
    # What does your project relate to?
    keywords="synchrotron analysis x-ray scattering tomography ",
    # You can just specify the packages manually here if your project is
    # simple. Or you can use find_packages().
    packages=[
        "xicam.gui",
        "xicam.gui.cammart",
        "xicam.gui.settings",
        "xicam.gui.static",
        "xicam.gui.widgets",
        "xicam.gui.windows",
        "xicam.gui.patches",
        "xicam.gui.clientonlymodels",
        "xicam.gui.utils",
    ],
    package_dir={},
    # Alternatively, if you want to distribute just a my_module.py, uncomment
    # this:
    #   py_modules=["my_module"],
    # List run-time dependencies here.  These will be installed by pip when
    # your project is installed. For an analysis of "install_requires" vs pip's
    # requirements files see:
    # https://packaging.python.org/en/latest/requirements.html
    install_requires=["qtpy", "pathlib", "pyqtgraph", "qdarkstyle", "qtmodern", "qtconsole", "xicam.plugins", "xicam.core"]
    + pyqt,
    setup_requires=[],
    # List additional groups of dependencies here (e.g. development
    # dependencies). You can install these using the following syntax,
    # for example:
    # $ pip install -e .[dev,tests]
    extras_require={
        # 'dev': ['check-manifest'],
        "tests": ["pytest", "coverage"]
    },
    # If there are data files included in your packages that need to be
    # installed, specify them here.  If using Python 2.6 or less, then these
    # have to be included in MANIFEST.in as well.
    package_data={},
    # Although 'package_data' is the preferred approach, in some case you may
    # need to place data files outside of your packages. See:
    # http://docs.python.org/3.4/distutils/setupscript.html#installing-additional-files # noqa
    # In this case, 'data_file' will be installed into '<sys.prefix>/my_data'
    # data_files=[#('lib/python2.7/site-packages/gui', glob.glob('gui/*')),
    #            ('lib/python2.7/site-packages/yaml/tomography',glob.glob('yaml/tomography/*'))],
    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # pip to create the appropriate form of executable for the target platform.
    entry_points={},
    ext_modules=[],
    include_package_data=True,
)
