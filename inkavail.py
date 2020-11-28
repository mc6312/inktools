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
from math import sqrt
from colorsys import rgb_to_hls


VERSION = '1.4.0'
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
RX_INK_COLOR = re.compile('^цвет:\s+#([0-9,a-f]{6})$', re.UNICODE|re.IGNORECASE)


class ColorValue():
    # строим велосипед, т.к. Gdk.RGBA с какого-то чорта уродуется внутри Gtk.ListStore

    #__slots__ = 'r', 'g', 'b'

    def __init__(self, r, g, b):
        self.r = r
        self.g = g
        self.b = b

        # Т.к. colorsys.rgb_to_hls() пытается определить диапазон значений
        # (м.б. как 0.0-1.0, так и 0-255) - у этой функции случаются
        # ошибки при значениях <=1, а потому принудительно приводим
        # входные значения к диапазону 0.0-1.0, а выходные - к
        # h: 0-359, l: 0-100, s: 0-100.
        self.h, self.l, self.s = rgb_to_hls(self.r / 255, self.g / 255, self.b / 255)
        self.h = int(round(self.h * 359))
        self.l = int(round(self.l * 100))
        self.s = int(round(self.s * 100))

        self.hexv = self.get_hex_value(self.r, self.g, self.b)

        self.navg = 0
        self.ravg = 0.0
        self.gavg = 0.0
        self.bavg = 0.0

    def __eq__(self, other):
        return (self.r == other.r) and (self.g == other.g) and (self.b == other.b)

    @staticmethod
    def get_int_value(r, g, b):
        """Возвращает 32-битное значение вида 0xRRGGBBAA,
        которое можно скормить Pixbuf.fill()."""

        return (r << 24) | (g << 16) | (b << 8) | 0xff

    @staticmethod
    def get_rgb32_value(v):
        """Возвращает 32-битное значение вида 0xRRGGBBAA,
        которое можно скормить Pixbuf.fill().
        Используются 24 бита значения v."""

        return ((v & 0xffffff) << 8) | 0xff

    @classmethod
    def new_from_rgb24(cls, rgb):
        """Создаёт экземпляр ColorValue из целого 0xRRGGBB."""

        return cls((rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255)

    def __int__(self):
        return self.get_int_value(self.r, self.g, self.b)

    def __repr__(self):
        return '%s(r=%d, g=%d, b=%d, h=%d, l=%d, s=%d, hex=%s)' % (self.__class__.__name__,
            self.r, self.g, self.b, self.h, self.l, self.s, self.hexv)

    def get_values(self):
        return (self.r, self.g, self.b)

    @staticmethod
    def get_hex_value(r, g, b):
        return '#%.2x%.2x%.2x' % (r, g, b)

    HUE_NAMES = (
        (12,  'красный'),
        (35,  'оранжевый'),
        (65,  'жёлтый'),
        (85,  'жёлто-зелёный'),
        (135, 'зелёный'),
        (165, 'бирюзовый'),
        (215, 'голубой'),
        (240, 'синий'),
        (265, 'фиолетово-синий'),
        (305, 'фиолетовый'),
        (335, 'красно-фиолетовый'),
        (360, 'красный'))

    LIGHTNESS_NAMES = (
        (5,   'близкий к чёрному'),
        (12,  'очень тёмный'),
        (20,  'тёмный'),
        (65,  'светлый'),
        (100, 'яркий'))

    SATURATION_NAMES = (
        (5,   'ненасыщенный'),
        (12,  'слабо насыщенный'),
        (45,  'средне-насыщенный'),
        (100,  'насыщенный'))

    def get_description(self):
        """Возвращает текстовое описание цвета (как умеет, хехе).
        Соответствие названий цветов и т.п. значениям HLS - чистый
        авторский произвол.
        Соответствия Pantone/RAL/... на данный момент нет, и, вероятно,
        не будет."""

        def __getv(fromlst, v):
            for vrange, vstr in fromlst:
                if v <= vrange:
                    return vstr

            return fromlst[-1][1]

        # костыль для тёмных малонасыщенных цветов
        if self.s <= 3:
            if self.l <= 4:
                desc = 'чёрный'
            elif self.l >= 90:
                desc = 'белый'
            else:
                desc = '%s серый' % __getv(self.LIGHTNESS_NAMES, self.l)
        else:
            desc = '%s, %s (%d%%), %s (%d%%)' % (
                __getv(self.HUE_NAMES, self.h),
                __getv(self.SATURATION_NAMES, self.s), self.s,
                __getv(self.LIGHTNESS_NAMES, self.l), self.l)

        return '%s; %s' % (self.hexv, desc)

    def avg_color_add(self, colorv):
        """Накопление значений для вычисления среднего цвета.
        colorv - экземпляр ColorValue."""

        self.ravg += colorv.r * colorv.r
        self.gavg += colorv.g * colorv.g
        self.bavg += colorv.b * colorv.b

        self.navg += 1

    def avg_color_reset(self):
        """Сброс переменных для вычисления среднего цвета."""

        self.navg = 0
        self.ravg = 0.0
        self.gavg = 0.0
        self.bavg = 0.0

    def avg_color_get(self):
        """Вычисляет среднее значение цвета,
        на основе значений, добавленных avg_color_add().
        Если не из чего было считать - возвращает None,
        иначе - экземпляр ColorValue."""

        if self.navg:
            return ColorValue(int(sqrt(self.ravg / self.navg)),
                              int(sqrt(self.gavg / self.navg)),
                              int(sqrt(self.bavg / self.navg)))
        else:
            return


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

        #
        # обрабатываем специальные подветви
        #

        def __get_special_text_node(headname):
            """Ищет ветвь типа OrgHeadlineNode с текстом заголовка headname,
            нерекурсивно ищет в ней вложенные ветви типа OrgTextNode.
            Возвращает список экземпляров OrgTextNode, если чего-нибудь
            находит, иначе - пустой список."""

            retl = []

            hlnode = node.find_child_by_text(headname, OrgHeadlineNode)
            if hlnode:
                for child in hlnode.children:
                    # isinstance тут не годится
                    if type(child) is OrgTextNode:
                        retl.append(child)

            return retl


        #
        # параметры
        #
        node.color = None

        params = __get_special_text_node('параметры')
        for paramnode in params:
            # цвет чернил 0xRRGGBB
            # в документе не хранится, используется только статистикой
            rm = RX_INK_COLOR.match(paramnode.text)

            if rm:
                node.color = int(rm.group(1), 16)

        #
        # наличие
        #

        # в документе не хранится - используется только статистикой
        node.avail = False
        node.availMl = 0.0
        node.availCartridges = False

        avails = __get_special_text_node('в наличии')
        for availnode in avails:
            rm = RX_AVAIL_ML.match(availnode.text)
            if rm:
                try:
                    avail = float(rm.group(1))

                    node.avail = True
                    node.availMl += avail
                    self.availMl += avail
                except ValueError:
                    pass
            else:
                rm = RX_AVAIL_CR.match(availnode.text)
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

        #
        # скармливаем всё, что следует, статистике "по тэгам"
        #
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


def __test_colordesc():
    colors = ((0, 0, 0),
        (255, 255, 255),
        (255, 0, 0),
        (255, 192, 0),
        (0, 0, 255),
        (0, 192, 255),
        (255, 0, 255),
        (20, 20, 20),
        (20, 20, 50),
        (96, 96, 255),
        (192, 192, 255),
        (96, 220, 255),
        (240, 240, 255))

    for r, g, b in colors:
        colorv = ColorValue(r, g, b)
        print(colorv.hexv, colorv.get_description())


if __name__ == '__main__':
    print('[testing %s]' % __file__)
    #__test_stats()
    __test_colordesc()
