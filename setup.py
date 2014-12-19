# -*- coding: utf-8 -*-
from setuptools import setup, Extension, find_packages

import sys
if sys.version_info < (3,):
    print("Sorry, Python 2 is not supported")
    sys.exit(1)


long_desc = """\
Bam Asset Manager is a tool to manage assets in Blender.
"""

requires = ['requests>=2.4']


import bam

setup(
    name='blender-bam',
    version=bam.__version__,
    url='http://developer.blender.org/project/view/55',
    download_url='https://pypi.python.org/pypi/blender-bam',
    license='GPLv2+',
    author='Campbell Barton, Francesco Siddi',
    author_email='ideasman42@gmail.com',
    description='Bam Asset Manager',
    long_description=long_desc,
    zip_safe=False,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Topic :: Utilities',
    ],
    platforms='any',
    packages=['bam'],
    include_package_data=True,
    package_data={
        '': ['*.txt', '*.rst'],
        },
    entry_points={
        'console_scripts': [
            'bam = bam:main',
        ],
    },
    install_requires=requires,
)

