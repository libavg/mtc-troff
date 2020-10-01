#!/usr/bin/env python
# -*- coding: utf-8 -*-

from distutils.core import setup

setup(
    name='TROff',
    version='1.0',
    author='Thomas Schott',
    author_email='<scotty at c-base dot org>',
    url='https://www.libavg.de/',
    license='GPL3',
    packages=['mttroff'],
    scripts=['scripts/mttroff'],
    package_data={
            'mttroff': ['media/preview.png', 'media/*.wav', 'data/*.pickle', 'fonts/Ubuntu-R.ttf']
    }
)
