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
    def __init__(self, stats, excludetags, includetags):
        """Параметры:
        excludetags     - None или множество строк с тэгами,
                          которые НЕ ДОЛЖНЫ попадать в выбор;
        includetags     - None или множество строк с тэгами,
                          которые ДОЛЖНЫ попадать в выбор.
        stats           - экземпляр inkavail.InkNodeStatistics.

        Поля:
        stats           - экземпляр inkavail.InkNodeStatistics;
        inks            - отфильтрованный (по меткам) список экземпляров)
                          OrgHeadlineNode с данными о чернилах, которые
                          есть в наличии."""

        self.stats = stats
        self.inks = []

        self.nInks = 0
        self.lastChoice = None

        self.filter_inks(excludetags, includetags)

    def filter_inks(self, excludetags, includetags):
        """Заполнение списка inks экземплярами OrgHeadlineNode
        с данными чернил, соответствующих меткам.

        Параметры:
        excludetags - None или множество строк с тэгами,
                      которые НЕ ДОЛЖНЫ попадать в выбор;
        includetags - None или множество строк с тэгами,
                      которые ДОЛЖНЫ попадать в выбор."""

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
            self.inks = list(filter(__filter_ink, self.stats.availInks))
        else:
            self.inks.clear()

        self.nInks = len(self.inks)

    def choice(self):
        """Возвращает случайный экземпляр OrgHeadlineNode
        (если было из чего выбирать) или None."""

        if self.nInks >= 2:
            # не присобачить ли счетчик на случай зацикливания ГПСЧ на одинаковом значении?
            while True:
                ink = random_choice(self.inks)
                if ink != self.lastChoice:
                    break
        elif self.nInks == 1:
            ink = self.nInks[0]
        else:
            ink = None

        self.lastChoice = ink

        return ink


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

    chooser = RandomInkChooser(stats, excludeTags, includeTags)

    ink = chooser.choice()
    if not ink:
        print('ничего подходящего не нашлось')
    else:
        inkName, inkTags, inkDescription, inkAvailability = stats.get_ink_description(ink)

        print('\033[1m%s (%s)\033[0m' % (inkName, inkTags))
        print(fill(inkDescription))
        if inkAvailability:
            print('\n\033[3mВ наличии: %s\033[0m' % inkAvailability)

    return 0


if __name__ == '__main__':
    sys.exit(__rc_main())
