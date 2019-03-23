#!/usr/bin/env python

from setuptools import setup, find_packages

desc = ''
with open('README.rst') as f:
    desc = f.read()

setup(
    name='disk_usage',
    version='0.0.2',
    description=('Utility to easily identify disk usage culprits.'),
    long_description=desc,
    url='https://github.com/josh-paul/disk_usage',
    author='Josh Paul',
    author_email='trevalen@me.com',
    license='Apache v2',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],

    keywords='disk usage disk_usage',
    packages=find_packages(exclude=['contrib', 'docs', 'test*']),
    install_requires=['dotted-dict', 'progress'],
    extras_require={},
    package_data={},
    data_files=[],
    entry_points={'console_scripts': ['disk_usage=disk.usage:cli']},
)
