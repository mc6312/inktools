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


import os.path
import sys
from orgmodeparser import *
import re


VERSION = '1.2.0'
TITLE = 'InkAvail'
TITLE_VERSION = '%s v%s' % (TITLE, VERSION)


MILLILITERS = 1000.0

""" InkTools-специфичные "расширения" формата Emacs OrgMode,
    не ломающие совместимость, т.к. для штатного парсера Emacs OrgMode
    являются простым текстом.

    Ветви дерева, содержащие описания чернил, должны иметь метку "ink".

    Статус ветвей:
    - не указан: чернила НЕ планируются к покупке (т.к. забракованы
      по какой-либо причине, в т.ч. по результатам испытаний)
    - TODO: чернила планируются к покупке и/или испытанию
    - DONE: чернила были куплены и испытаны

    Наличие чернил в коллекции описано отдельно (см. ниже) и статусом
    TODO/DONE/... не указывается.

    Данные, помещаемые в комментарии.
    После символа комментария обязателен пробел, чтобы стандартный парсер
    не спотыкался.

    @TAGSTAT Общий заголовок:заголовок 1го столбца:метка [... метка]

    Шаблон для вывода таблицы статистики, параметры разделяются символом ":".
    1й параметр - "общий заголовок" - название таблицы,
    2й параметр - заголовок 1го столбца,
    3й параметр - метки, разделённые пробелами

    Пример: # @TAGSTAT По цветам:Цвет:black blue blue_black gray green

    @TAGNAMES метка=название:[...:меткаN=названиеN:]

    Соответствие меток Emacs OrgMode (которые не могут содержать пробелов
    и некоторых других символов) и человекочитаемых строк, для отображения
    в таблицах статистики.

    Пример: # @TAGNAMES dark=тёмные:black=чёрные:blue=синие:blue_black=сине-чёрные:

    Дополнительно обрабатываются текстовые поля ветвей, имеющих название
    "в наличии" - в тексте ищутся строки вида "флакон NN мл" и/или
    "картридж".
"""


RX_AVAIL_ML = re.compile('^флакон\s([\d\.]+)\s?.*?$', re.UNICODE|re.IGNORECASE)
RX_AVAIL_CR = re.compile('.*картридж.*', re.UNICODE|re.IGNORECASE)


class TagStatInfo():
    class TagStatValue():
        __slots__ = 'available', 'unavailable', 'unwanted', 'inks'

        def __init__(self):
            self.available = 0
            self.unavailable = 0
            self.unwanted = 0
            self.inks = [] # список всех экземпляров OrgHeadlineNode, соответствующих тэгу

        def __repr__(self):
            return '%s(available=%d, unavailable=%d, unwanted=%d, inks=%s)' % (self.__class__.__name__,
                self.available, self.unavailable, self.unwanted, self.inks)

        def counter_strs(self):
            def __to_str(i):
                return '-' if i == 0 else str(i)

            return (__to_str(self.available), __to_str(self.unavailable), __to_str(self.unwanted))

    def __init__(self, totals, title, col1title, tags):
        """Параметры:
        totals      - экземпляр класса InkNodeStatistics,
                      которому принадлежит текущий экземпляр TagStatInfo;
        title       - название статистической таблицы;
        col1title   - название первого столбца;
        tags        - список меток, которые учитывать."""

        self.totalstats = totals
        self.title = title
        self.col1title = col1title
        self.tags = set(tags) # все метки, которые учитываем
        self.stats = dict() # ключ - метка, значение - экземпляр TagStatValue

    def __repr__(self):
        return '%s(title="%s", col1title="%s", tags=%s, stats=%s)' % (self.__class__.__name__,
            self.title, self.col1title, self.tags, self.stats)

    def gather_statistics(self, inknode):
        # учитываем чернила в статистике, если у них есть общие метки
        # с нашими
        ntags = set(inknode.tags) & self.tags

        for tag in ntags:
            if tag in self.stats:
                nfo = self.stats[tag]
            else:
                nfo = self.TagStatValue()
                self.stats[tag] = nfo

            if inknode.avail:
                nfo.available += 1
            else:
                # inknode.avail == False:
                nfo.unavailable += 1

            if inknode.done is None:
                nfo.unwanted += 1

            nfo.inks.append(inknode)


class InkNodeStatistics():
    def __init__(self, rootnode):
        self.availMl = 0.0

        # список экземпляров OrgHeadlineNode - чернила в наличии
        self.availInks = []

        # список экземпляров OrgHeadlineNode - отсутствующие чернила
        self.unavailInks = []

        # список экземпляров OrgHeadlineNode - нафиг не нужные чернила
        # (ветви, которые и не TODO, и не DONE)
        self.unwantedInks = []

        # список экземпляров TagStatInfo - статистика по тэгам
        self.tagStats = []

        # словарь переводов названий тэгов,
        # где ключ - тэг, а значение - перевод названия
        self.tagNames = {}

        self.scan_node(rootnode, 0)

        # список всех меток
        self.tags = []

        # ищем ветви типа OrgDirectiveNode только на верхнем уровне
        for node in rootnode.children:
            if isinstance(node, OrgDirectiveNode) and node.name == 'TAGS':
                self.tags += node.text.split(None)

    def get_tag_display_name(self, tag):
        return self.tagNames[tag] if tag in self.tagNames else tag

    def get_total_result_table(self):
        """Возвращает список списков, содержащих строки
        со значениями общей статистики."""

        totalMl = self.availMl

        if totalMl < MILLILITERS:
            units = 'мл'
        else:
            totalMl /= MILLILITERS
            units = 'л'

        inksAvail = len(self.availInks)
        inksUnavail = len(self.unavailInks)
        inksUnwanted = len(self.unwantedInks)
        inksTotal = inksAvail + inksUnavail

        def __percent(n):
            pc = '%.1f%%' % (0 if inksTotal == 0 else 100.0 * n / inksTotal)

            return (str(n), pc)

        # 4 столбца: название поля, абсолютное значение, процент от общего числа, объем в л/мл
        # объем указывается только для чернил в наличии, для прочих - пустые строки

        return [
                ['Всего:', str(inksTotal), '', ''],
                ['В наличии:', *__percent(inksAvail), '≈{:.2f} {:s}'.format(totalMl, units)],
                ['Отсутствуют:', *__percent(inksUnavail), ''],
                ['Не нужны:', *__percent(inksUnwanted), ''],
               ]

    def __repr__(self):
        return '%s(availMl=%.2f, availInks=%s, unavailInks=%s, unwantedInks=%s, tagStats=%s)' % (
            self.__class__.__name__,
            self.availMl,
            self.availInks,
            self.unavailInks,
            self.unwantedInks,
            self.tagStats)

    __RX_INK_COLOR = re.compile('^цвет:\s+#([0-9,a-f]{6})$', re.UNICODE|re.IGNORECASE)

    def get_ink_node_statistics(self, node):
        """Сбор статистики для node, если это OrgHeadlineNode с описание
        чернил.

        Возвращает True, если node содержало описание чернил, иначе False."""

        if not isinstance(node, OrgHeadlineNode):
            return False

        # учитываем только ветви, имеющие метку "ink"
        if 'ink' not in node.tags:
            return False

        # это "чернильный" элемент дерева - его содержимым кормим статистику

        # 0. обрабатываем служебные слова в тексте ветви
        tnode, rm = node.find_text_node_by_regex(self.__RX_INK_COLOR)

        # цвет чернил - в документе не хранится, используется только статистикой
        node.color = int(rm.group(1), 16) if rm else None

        # 1. собираем статистику по наличию чернил

        # в документе не хранится - используется только статистикой
        node.avail = False
        node.availMl = 0.0
        node.availCartridges = False

        availnode = node.find_child_by_text('в наличии', OrgHeadlineNode)
        if availnode is not None:
            for child in availnode.children:
                if type(child) is not OrgTextNode:
                    continue

                rm = RX_AVAIL_ML.match(child.text)
                if rm:
                    try:
                        avail = float(rm.group(1))

                        node.avail = True
                        node.availMl += avail
                        self.availMl += avail
                    except ValueError:
                        pass
                else:
                    rm = RX_AVAIL_CR.match(child.text)
                    if rm:
                        node.avail = True
                        node.availCartridges = True

        # Внимание:
        # node.avail НЕ зависит от node.done

        if node.avail:
            self.availInks.append(node)
        elif node.avail == False:
            self.unavailInks.append(node)

        # т.е. "нежелательные" могут одновременно быть в списках
        # avail/unavail!
        if node.done == None:
            self.unwantedInks.append(node)

        # 2. скармливаем их статистике "по тэгам"
        for tagstat in self.tagStats:
            tagstat.gather_statistics(node)

        return True

    def scan_node(self, node, level):
        """Рекурсивный обход дерева экземпляров OrgNode.
        Сбор статистики по наличию чернил.
        node    - экземпляр Org*Node;
        level   - уровень вложенности."""

        for child in node.children:
            if isinstance(child, OrgCommentNode):
                # для комментариев особая обработка:
                # на нулевом уровне ищем "самопальные "директивы вида
                # "@directive parameter [parameter]",
                # (см. метод process_directive)
                # на следующих ничего не делаем, один фиг там нет описаний чернил
                if level == 0:
                    dargs = list(map(lambda s: s.strip(), child.text.split(None, 1)))
                    if not dargs:
                        continue

                    dname = dargs[0]
                    if not dname.startswith('@'):
                        # просто комментарий или не наша директива
                        continue

                    dname = dname[1:]
                    if not dname:
                        # "@" без текста за директиву не считаем
                        continue

                    dargs = dargs[1:] # м.б. пустой список!

                    self.process_directive(dname, dargs[0] if dargs else '')

            elif not self.get_ink_node_statistics(child):
                self.scan_node(child, level + 1)

    def __process_tagstat_directive(self, dvalue):
        # статистика по тэгам
        # формат заголовка -
        # "название таблицы:название 1го столбца:метка1 [... [меткаN]]"

        tsargs = list(map(lambda s: s.strip(), dvalue.split(':', 2)))

        #TODO присобачить проверку ошибок синтаксиса
        if len(tsargs) != 3:
            return

        tstitle = tsargs[0]
        if not tstitle:
            return

        tsc1title = tsargs[1]
        if not tsc1title:
            return

        tstags = set(filter(None, map(lambda s: s.strip(), tsargs[2].split(None))))
        if not tstags:
            return

        self.tagStats.append(TagStatInfo(self, tstitle, tsc1title, tstags))

    def __process_tagnames_directive(self, dvalue):
        # переводы названий тэгов в формате
        # tagname=translation[:tagname1=translation1[...:tagnameN=translationN]

        for rawtrans in dvalue.split(':'):
            tagname, sep, tagtrans = map(lambda s: s.strip(), rawtrans.partition('='))

            #TODO прикрутить обработку ошибок синтаксиса
            if sep != '=' or not tagname or not tagtrans:
                continue

            self.tagNames[tagname] = tagtrans

    def process_directive(self, dname, dvalue):
        """Обработка "самопальной" (не стандарта OrgMode) директивы вида
        '@ИМЯ значение'.

        dname   - имя директивы (без символа @),
        dvalue  - значение директивы.

        Имена директив регистро-зависимы.
        В случае ошибок генерируются исключения."""

        if dname == 'TAGSTAT':
            self.__process_tagstat_directive(dvalue)
        elif dname == 'TAGNAMES':
            self.__process_tagnames_directive(dvalue)

    def get_ink_description(self, ink):
        """Получение описания чернил.

        Параметры:
            ink         - экземпляр OrgHeadlineNode.

        Возвращает кортеж из четырёх строк:
        'название', 'отсортированный список человекочитаемых меток',
        'описание', 'наличие'."""

        if not isinstance(ink, OrgHeadlineNode):
            raise TypeError('get_ink_description(ink): "ink" must be OrgHeadlineNode')

        if 'ink' not in ink.tags:
            raise ValueError('get_ink_description(ink): "ink" must contain ink description')

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
                ', '.join(sorted(map(lambda tag: self.tagNames[tag] if tag in self.tagNames else tag, disptags))),
                '\n'.join(desc),
                ' и '.join(avails))


def print_table(headers, printheader, table):
    """Вывод в stdout отформатированной таблицы.

    headers     - список кортежей, содержащих по две строки:
                  1. текст заголовка;
                  2. символ выравнивания для форматирования;
    printheader - булевское значение, False - не печатать заголовок;
    table       - список списков, содержащих строки."""

    #TODO м.б. стоит присобачить проверку правильности параметров

    widths = [0] * len(headers)

    def update_widths(row):
        for col, s in enumerate(row):
            sl = len(s)
            if sl > widths[col]:
                widths[col] = sl

    header = []

    header = list(map(lambda v: v[0], headers))
    update_widths(header)

    for r in table:
        update_widths(r)

    tabfmt = '  '.join(list(map(lambda h: '{:%s%ds}' % (h[1][1], widths[h[0]]), enumerate(headers))))

    if printheader:
        print(tabfmt.format(*header))

    for r in table:
        print(tabfmt.format(*r))




def load_ink_db(fname):
    if not fname:
        print('Файл не указан')
        return None

    if not os.path.exists(fname):
        print('Файл "%s" не найден' % fname)
        return None

    #print(f'Загружаю {fname}')
    return MinimalOrgParser(fname)


def get_ink_stats(db):
    return InkNodeStatistics(db) if db is not None else None


def process_cmdline():
    #TODO м.б. присобачить нормальную обработку командной строки

    if len(sys.argv) < 2:
        fname = 'inks.org'
    else:
        fname = os.path.expanduser(sys.argv[1])

    return fname


def __test_stats():
    #TODO присобачить файл настроек с указанием файла БД

    print('%s\n' % TITLE_VERSION)

    stats = get_ink_stats(load_ink_db(process_cmdline()))
    if stats:
        print(stats.get_total_result_table())

        for tagstat in stats.tagStats:
            print('\n%s' % tagstat.title)
            print(tagstat.stats)

    return 0


if __name__ == '__main__':
    print('[testing %s]' % __file__)
    __test_stats()
