#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import os.path
import sys
from orgmodeparser import *
import re


VERSION = '1.0.1'
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
        __slots__ = 'available', 'unavailable'

        def __init__(self):
            self.available = 0
            self.unavailable = 0

        def __repr__(self):
            return '%s(available=%d, unavailable=%d)' % (self.__class__.__name__,
                self.available, self.unavailable)

    def __init__(self, title, col1title, tags):
        """Параметры:
        title       - название статистической таблицы,
        col1title   - название первого столбца,
        tags        - список меток, которые учитывать."""

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

            if inknode.done == True:
                nfo.available += 1
            elif inknode.done == False:
                nfo.unavailable += 1
            # inknode.done == None игнорируем


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

        # 1. скармливаем их статистике "по тэгам"
        for tagstat in self.tagStats:
            tagstat.gather_statistics(node)

        # 2. собираем статистику по наличию чернил

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

        self.tagStats.append(TagStatInfo(tstitle, tsc1title, tstags))

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


def print_total_statistics(stats):
    totalMl = stats.availMl

    if totalMl < MILLILITERS:
        units = 'мл'
    else:
        totalMl /= MILLILITERS
        units = 'л'

    inksAvail = len(stats.availInks)
    inksUnavail = len(stats.unavailInks)
    inksUnwanted = len(stats.unwantedInks)
    inksTotal = inksAvail + inksUnavail

    def __percent(n):
        pc = 0 if inksTotal == 0 else 100.0 * n / inksTotal
        return '%d (%.1f%%)' % (n, pc)

    print(f'''Всего:       {inksTotal}
В наличии:   {__percent(inksAvail)}, ≈{totalMl:.2f} {units}
Отсутствуют: {__percent(inksUnavail)}
Не нужны:    {__percent(inksUnwanted)}''')

    #for node in stats.unavailInks:
    #    print(f'  {node.text}')


def print_tag_statistics(stats):
    def print_stat_table(tagstat):
        print(f'\n{tagstat.title}:')

        widths = [0, 0, 0]

        def update_widths(r):
            for col, s in enumerate(r):
                sl = len(s)
                if sl > widths[col]:
                    widths[col] = sl

        table = [(tagstat.col1title, 'Есть', 'Нет')]
        update_widths(table[0])

        def __to_str(i):
            return '-' if i == 0 else str(i)

        for tag, nfo in sorted(tagstat.stats.items(), key=lambda r: r[1].available, reverse=True):
            rec = (stats.tagNames[tag] if tag in stats.tagNames else tag,
                __to_str(nfo.available),
                __to_str(nfo.unavailable))

            update_widths(rec)
            table.append(rec)

        tformat = '  {:<%ds}  {:>%ds}  {:>%ds}' % (*widths,)

        for rec in table:
            print(tformat.format(*rec))

    for tagstat in stats.tagStats:
        print_stat_table(tagstat)


def load_ink_stats():
    #fname = os.path.expanduser('~/shareddocs/doc/upgrade/inks.org')
    fname = 'inks.org'
    if not os.path.exists(fname):
        return 2

    #print(f'Загружаю {fname}')
    rootnode = MinimalOrgParser(fname)

    return InkNodeStatistics(rootnode)


def main(args):
    stats = load_ink_stats()

    print_total_statistics(stats)
    print_tag_statistics(stats)

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
