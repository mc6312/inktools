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
from random import choice as random_choice
from textwrap import fill

from inkavail import *


class RandomInkChooser():
    def __init__(self, stats):
        """Параметры:
        stats       - экземпляр inkavail.InkNodeStatistics"""

        self.stats = stats

    def choice(self, excludetags, includetags):
        """Параметры:
        excludetags - множество строк с тэгами, которые НЕ должны попадать в выбор;
        includetags - множество строк с тэгами, которые должны попадать в выбор.

        Возвращает экземпляр OrgHeadlineNode (если было из чего выбират)
        или None."""

        def __filter_ink(ink):
            """Параметры:
            ink         - экземпляр OrgHeadlineNode;

            Возвращает булевское значение (True, если ink соответствует
            заданным параметрам)."""

            if ink.availMl < 0.0 and not ink.availCartridges:
                return False

            inkTags = set(map(lambda s: s.lower(), ink.tags))

            if excludetags and not inkTags.isdisjoint(excludetags):
                return False

            if includetags and not inkTags.isdisjoint(includetags):
                return False

            return True

        if self.stats:
            inks = list(filter(__filter_ink, self.stats.availInks))

            if inks:
                return random_choice(inks)

        return None

    def get_ink_description(self, ink):
        """Получение описания чернил.

        Параметры:
            ink         - экземпляр OrgHeadlineNode.

        Возвращает кортеж из четырёх строк:
        'название', 'отсортированный список человекочитаемых меток',
        'описание', 'наличие'."""

        desc = []

        for chld in ink.children:
            if isinstance(chld, OrgTextNode):
                desc.append(chld.text)

        avails = []

        if ink.availMl > 0.0:
            if ink.availMl < 500.0:
                avs = '%.f мл' % ink.availMl
            else:
                avs = '%.2f л' % (ink.availMl / 1000.0)
            avails.append(avs)

        if ink.availCartridges:
            avails.append('картриджи')

        # некоторый костылинг
        disptags = ink.tags.copy()
        # удаляем служебную метку - она нужна при загрузке БД, не для отображения
        disptags.remove('ink')

        return (ink.text,
                ', '.join(sorted(map(lambda tag: self.stats.tagNames[tag] if tag in self.stats.tagNames else tag, disptags))),
                '\n'.join(desc),
                ' и '.join(avails))


def __rc_main():
    #TODO присобачить файл настроек с указанием файла БД

    print('%s\n' % TITLE_VERSION)

    stats = get_ink_stats(load_ink_db(process_cmdline()))

    if not stats.availInks:
        print('Нет чернил - не из чего выбирать')
        return 0

    excludeTags = set()
    includeTags = set()

    for arg in sys.argv[1:]:
        arg = arg.lower()

        if arg.startswith('!'):
            excludeTags.add(arg[1:])
        else:
            includeTags.add(arg)

    chooser = RandomInkChooser(stats)

    ink = chooser.choice(excludeTags, includeTags)
    if not ink:
        print('ничего подходящего не нашлось')
    else:
        inkName, inkTags, inkDescription, inkAvailability = chooser.get_ink_description(ink)

        print('\033[1m%s (%s)\033[0m' % (inkName, inkTags))
        print(fill(inkDescription))
        if inkAvailability:
            print('\n\033[3mВ наличии: %s\033[0m' % inkAvailability)

    return 0


if __name__ == '__main__':
    sys.exit(__rc_main())
