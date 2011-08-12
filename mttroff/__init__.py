#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Init script for TROff - A Multitouch TRON Clone
#
# Copyright (C) 2011 Thomas Schott, <scotty at c-base dot org>
#
# TROff is free software: You can redistribute it and/or
# modify it under the terms of the GNU General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# TROff is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with TROff. If not, see <http://www.gnu.org/licenses/>.

from os import path
from libavg.utils import getMediaDir, createImagePreviewNode
from troff import TROff

__all__ = [ 'apps', 'TROff']

def createPreviewNode(maxSize):
    filename = path.join(getMediaDir(__file__), 'preview.png')
    return createImagePreviewNode(maxSize, absHref = filename)

apps = (
        {'class': TROff,
            'createPreviewNode': createPreviewNode},
        )
