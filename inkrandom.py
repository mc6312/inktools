#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" inkavail.py

    This file is part of InkTools.

    InkTools is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    InkTools is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with InkTools.  If not, see <http://www.gnu.org/licenses/>."""



import sys
from inkavail import *
from random import choice as random_choice
from textwrap import fill


def main(args):
    stats = load_ink_stats()

    if not stats.availInks:
        print('Нет чернил - не из чего выбирать')
        return 0

    excludeTags = set()
    includeTags = set()

    for arg in args[1:]:
        arg = arg.lower()

        if arg.startswith('!'):
            excludeTags.add(arg[1:])
        else:
            includeTags.add(arg)

    def filter_ink(ink):
        if ink.availMl < 0.0 and not ink.availCartridges:
            return False

        inkTags = set(map(lambda s: s.lower(), ink.tags))

        if excludeTags and not inkTags.isdisjoint(excludeTags):
            return False

        if includeTags and not inkTags.isdisjoint(includeTags):
            return False

        return True

    inks = list(filter(filter_ink, stats.availInks))

    ink = random_choice(inks)
    print('\n\033[1m%s (%s)\033[0m' % (ink.text, ', '.join(sorted(map(lambda tag: stats.tagNames[tag] if tag in stats.tagNames else tag, ink.tags)))))

    for chld in ink.children:
        if isinstance(chld, OrgTextNode):
            print(fill(chld.text))

    if ink.availMl > 0.0:
        if ink.availMl < 500.0:
            avs = '%.f мл' % ink.availMl
        else:
            avs = '%.2f л' % (ink.availMl / 1000.0)
    elif ink.availCartridges:
        avs = 'картриджи'
    else:
        avs = None

    if avs:
        print('\n\033[3mВ наличии: %s\033[0m' % avs)

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
