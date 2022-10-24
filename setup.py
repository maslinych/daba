#!/usr/bin/env python3
# coding: utf-8
"""Daba — Pattern-based morphemic analysis toolkit
"""

# Always prefer setuptools over distutils
from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

# Arguments marked as "Required" below must be included for upload to PyPI.
# Fields marked as "Optional" may be commented out.

setup(
    name='daba',  # Required
    version='0.9.3',  # Required
    description='Pattern-based morphemic analysis toolkit',  # Required
    long_description=long_description,  # Optional
    url='https://github.com/maslinych/daba',  # Optional

    # This should be your name or the name of the organization which owns the
    # project.
    author='Kirill Maslinsky',  # Optional

    # This should be a valid email address corresponding to the author listed
    # above.
    # author_email='kirill@altlinux.org',  # Optional

    # Classifiers help users find your project by categorizing it.
    #
    # For a list of valid classifiers, see
    # https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[  # Optional
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 4 - Beta',

        # Indicate who your project is intended for
        'Intended Audience :: Science/Research',
        'Topic :: Text Processing :: Linguistic',
        'Natural Language :: Bambara',

        # Pick your license as you wish (should match "license" above)
        # FIXME: LICENSE
        'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9'
    ],
    # supprted python versions
    python_requires='>=3.6',
    # This field adds keywords for your project which will appear on the
    # project page. What does your project relate to?
    #
    # Note that this is a string of words separated by whitespace, not a list.
    keywords='nlp linguistics',  # Optional

    # You can just specify package directories manually here if your project is
    # simple. Or you can use find_packages().
    #
    # Alternatively, if you just want to distribute a single Python file, use
    # the `py_modules` argument instead as follows, which will expect a file
    # called `my_module.py` to exist:
    #
    #   py_modules=["my_module"],
    #
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),  # Required

    # This field lists other packages that your project depends on to run.
    # Any package you put here will be installed by pip when your project is
    # installed, so they must be valid existing projects.
    #
    # For an analysis of "install_requires" vs pip's requirements files see:
    # https://packaging.python.org/en/latest/requirements.html
    install_requires=[
        'funcparserlib',
        'intervaltree',
        'pytrie',
        'regex',
        'attrdict3',
        'wxPython',
    ],
    # List additional groups of dependencies here (e.g. development
    # dependencies). Users will be able to install these using the "extras"
    # syntax, for example:
    #
    #   $ pip install sampleproject[dev]
    #
    # Similar to `install_requires` above, these must be valid existing
    # projects.
    extras_require={  # Optional
        'dev': ['check-manifest'],
        'test': ['coverage'],
        'ml': [
            'python-Levenshtein',
            'nltk',
            'python-crfsuite',
        ]
    },

    # If there are data files included in your packages that need to be
    # installed, specify them here.
    #
    # If using Python 2.6 or earlier, then these have to be included in
    # MANIFEST.in as well.
    # package_data={  # Optional
    #    'sample': ['package_data.dat'],
    # },

    # Although 'package_data' is the preferred approach, in some case you may
    # need to place data files outside of your packages. See:
    # http://docs.python.org/3.4/distutils/setupscript.html#installing-additional-files
    #
    # In this case, 'data_file' will be installed into '<sys.prefix>/my_data'
    # data_files=[('my_data', ['data/data_file'])],  # Optional

    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # `pip` to create the appropriate form of executable for the target
    # platform.
    #
    # For example, the following would provide a command called `sample` which
    # executes the function `main` from this package when invoked:
    entry_points={  # Optional
        'console_scripts': [
            'metaprint=daba.metaprint:main',
            'mparser=daba.mparser:main',
            'wordparser=daba.wordparser:main',
            'dabased=daba.dabased:main',
            'daba2align=daba.daba2align:main'
        ],
        'gui_scripts': [
            'meta=daba.meta:main',
            'gparser=daba.gparser:main',
            'gdisamb=daba.gdisamb:main',
        ],
        'daba.plugins': [
            'apostrophe = daba.plugins.apostrophe',
            'bailleul = daba.plugins.bailleul',
            'bamlatinold = daba.plugins.bamlatinold',
            'emklatinold = daba.plugins.emklatinold',
            'nko = daba.plugins.nko',
            'vydrine = daba.plugins.vydrine',
            'danoldtonew = daba.plugins.danoldtonew',
            'mwanipatopractical = daba.plugins.mwanipatopractical',
            'kpellemkoldtonew = daba.plugins.kpelle',
            'kpelleoldtopract = daba.plugins.kpelle'
        ]
    },
)
