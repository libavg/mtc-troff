#!/usr/bin/env python
# -*- coding: utf-8 -*-

from distutils.core import setup

setup(
    name='TROff',
    version='1.0',
    author='Thomas Schott',
    author_email='<scotty at c-base dot org>',
    license='GPL3',
    packages=['troff'],
    scripts=['scripts/troff'],
    package_data={
            'troff': ['media/preview.png', 'media/*.wav', 'data/*.pickle', 'fonts/Millennium.ttf']
    }
)
