#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" inkavailui.py

    Copyright 2020 MC-6312 <mc6312@gmail.com>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>."""


from gtktools import *

from gi.repository import Gtk #, Gdk, GObject, Pango, GLib
from gi.repository.GLib import markup_escape_text

from gtkchecklistbox import CheckListBox

import sys
import os.path
from shutil import which
from subprocess import Popen

from inkavail import *
from inkrandom import RandomInkChooser


class MainWnd():
    PAGE_STAT, PAGE_CHOICE = range(2)

    INCLUDE_ANY = 'любые'
    EXCLUDE_NOTHING = 'никаких'

    def wnd_destroy(self, widget):
        Gtk.main_quit()

    def __init__(self, fname):
        #
        resldr = get_resource_loader()
        uibldr = get_gtk_builder(resldr, 'inkavail.ui')

        self.dbfname = fname
        self.db = None
        self.rndchooser = None
        self.stats = None

        # для выбора в случайном выбираторе
        self.includetags = set()
        self.excludetags = set()

        #
        # основное окно
        #
        self.window = uibldr.get_object('inkavailwnd')
        icon = resldr.load_pixbuf_icon_size('inktools.svg', Gtk.IconSize.DIALOG, 'computer')
        self.window.set_icon(icon)

        self.headerbar = uibldr.get_object('headerbar')

        self.headerbar.set_title(TITLE_VERSION)

        #
        self.pages = uibldr.get_object('pages')

        self.totalstatlstore, self.totalstatview = get_ui_widgets(uibldr,
            'totalstatlstore', 'totalstatview')

        self.detailstatststore, self.detailstatsview, detailstatswnd = get_ui_widgets(uibldr,
            'detailstatststore detailstatsview detailstatswnd')

        # костылинг
        detailstatswnd.set_min_content_height(WIDGET_BASE_HEIGHT * 24)

        self.openorgfiledlg = uibldr.get_object('openorgfiledlg')

        self.randominkname, self.randominktags, self.randominkdesc, self.randominkavail = get_ui_widgets(uibldr,
            'randominkname randominktags randominkdesc randominkavail')
        self.randominkdescbuf = self.randominkdesc.get_buffer()

        # грязный хакЪ из-за ошибки в Glade 3.22.2, криво генерирующей элементы меню со значками
        mnuFile = uibldr.get_object('mnuFile')
        img = Gtk.Image.new_from_icon_name('open-menu-symbolic', Gtk.IconSize.MENU)
        mnuFile.add(img)

        #
        self.includetagstxt, self.excludetagstxt, self.tagchooserdlg = get_ui_widgets(uibldr,
            'includetagstxt', 'excludetagstxt', 'tagchooserdlg')

        self.tagchecklistbox = CheckListBox(selectionbuttons=True)
        # костыль
        # потому что set_min_content_width с какого-то хрена не работает
        self.tagchecklistbox.scwindow.set_size_request(WIDGET_BASE_WIDTH * 80, WIDGET_BASE_HEIGHT * 10)
        #self.tagchecklistbox.scwindow.set_min_content_width(WIDGET_BASE_WIDTH * 90)
        #self.tagchecklistbox.scwindow.set_min_content_height(WIDGET_BASE_HEIGHT * 16)

        taglistvbox = self.tagchooserdlg.get_content_area()
        taglistvbox.pack_start(self.tagchecklistbox, True, True, 0)

        #
        #mnuFileEdit = uibldr.get_object('mnuFileEdit')
        self.emacs = which('emacs')
        self.emacsProcess = None

        #
        uibldr.connect_signals(self)

        self.load_db()

        self.window.show_all()

    def load_db(self):
        self.totalstatview.set_model(None)
        self.totalstatlstore.clear()

        self.detailstatsview.set_model(None)
        self.detailstatststore.clear()

        try:
            self.db = load_ink_db(self.dbfname)
            self.stats = get_ink_stats(self.db)
            self.rndchooser = None

            # статистика
            if self.stats:
                dfname = os.path.split(self.dbfname)[-1]

                # общая статистика
                totals = self.stats.get_total_result_table()

                for row in totals:
                    self.totalstatlstore.append(row)

                # детали
                for tagstat in self.stats.tagStats:
                    itr = self.detailstatststore.append(None, (tagstat.title, '', '', ''))

                    for row in tagstat.get_stat_table():
                        self.detailstatststore.append(itr, row)

                #TODO когда-нибудь потом прикрутить тэги для выбора
                self.rndchooser = RandomInkChooser(self.stats, None, None)

            else:
                dfname = ''

            #
            # метки
            #
            self.tagchecklistbox.clear_items()

            def __add_tag(tagname):
                tagdisp = tagname if tagname not in self.stats.tagNames else self.stats.tagNames[tagname]
                self.tagchecklistbox.add_item(False, tagdisp, tagname)

            # в первую очередь используем только метки, учитываемые в статистике
            ntags = 0

            for tsinfo in self.stats.tagStats:
                for tagname in sorted(tsinfo.tags):
                    __add_tag(tagname)
                    ntags += 1

            # ...а вот если там меток не было - берём весь список меток
            if not ntags:
                for tagname in sorted(self.stats.tags):
                    __add_tag(tagname)

            self.includetags.clear() # пустое множество - выбирать все
            self.excludetags.clear() # пустое множество - не исключать ничего

            self.includetagstxt.set_text(self.INCLUDE_ANY)
            self.excludetagstxt.set_text(self.EXCLUDE_NOTHING)

            #

            self.openorgfiledlg.select_filename(self.dbfname)
            self.headerbar.set_subtitle(dfname)

        finally:
            self.detailstatsview.set_model(self.detailstatststore)
            self.detailstatsview.expand_all()
            self.totalstatview.set_model(self.totalstatlstore)

        self.choose_random_ink()

    def choose_random_ink(self):
        if self.rndchooser is None:
            inknamet = '...'
            inkdesct = ''
            inkavailt = ''
        else:
            self.rndchooser.filter_inks(self.excludetags, self.includetags)

            ink = self.rndchooser.choice()

            if not ink:
                inknamet = 'ничего подходящего не нашлось'
                inktagst = '-'
                inkdesct = ''
                inkavailt = '-'
            else:
                inkName, inkTags, inkDescription, inkAvailability = self.stats.get_ink_description(ink)

                inknamet = '<b>%s</b>' % markup_escape_text(inkName)
                inktagst = markup_escape_text(inkTags) if inkTags else '-'
                inkdesct = inkDescription
                inkavailt = markup_escape_text(inkAvailability)

        self.randominkname.set_markup(inknamet)
        self.randominktags.set_markup(inktagst)
        self.randominkdescbuf.set_text(inkdesct)
        self.randominkavail.set_markup(inkavailt)

    def randomchbtn_clicked(self, btn):
        self.choose_random_ink()

    def mnuRandomChoice_activate(self, wgt):
        self.choose_random_ink()
        self.pages.set_current_page(self.PAGE_CHOICE)

    def select_load_db(self):
        self.openorgfiledlg.show_all()
        r = self.openorgfiledlg.run()
        self.openorgfiledlg.hide()

        if r == Gtk.ResponseType.OK:
            fname = self.openorgfiledlg.get_filename()

            if fname != self.dbfname:
                self.dbfname = fname
                self.load_db()

            self.pages.set_current_page(self.PAGE_STAT)

    def mnuFileOpen_activate(self, mi):
        self.select_load_db()

    def mnuFileReload_activate(self, mi):
        if not self.dbfname:
            self.select_load_db()
        else:
            self.load_db()

    def mnuFileEdit_activate(self, wgt):
        self.start_editor()

    def __emacs_is_running(self):
        if self.emacsProcess is None:
            return False
        else:
            r = self.emacsProcess.poll()
            if r is None:
                return True
            else:
                self.emacsProcess = None
                return False

    def start_editor(self):
        def __msg(what):
            msg_dialog(self.window,
                       TITLE,
                       what)

        if not self.dbfname:
            __msg('Файл БД не выбран. Сначала выберите его...')
        elif not self.emacs:
            __msg('Для редактирования БД требуется редактор Emacs')
        elif self.__emacs_is_running():
            __msg('Редактор БД уже работает')
        else:
            try:
                self.emacsProcess = Popen([self.emacs, '--no-desktop', '--no-splash', self.dbfname])
            except Exception as ex:
                print('* %s' % str(ex), file=sys.stderr)
                __msg('Сбой запуска редактора БД')

    def select_tags(self, title, selfrom, disp, noselstr):
        """title    - строка с заголовком окна,
        selfrom     - list или set для чекбоксов (см. CheckListBox.set_selection()),
        disp        - экземпляр Gtk.Label для отображения результатов выбора;
        noselstr    - строка, которая должна отображаться, если в
                      CheckListBox не выбрано ни одного элемента."""

        self.tagchooserdlg.set_title(title)
        self.tagchooserdlg.show_all()
        self.tagchecklistbox.set_selection(selfrom)
        r = self.tagchooserdlg.run()
        self.tagchooserdlg.hide()

        if r == Gtk.ResponseType.OK:
            disps = self.tagchecklistbox.get_selection_titles()
            dt = ', '.join(disps) if disps else noselstr
            disp.set_text(dt)

            return self.tagchecklistbox.get_selection()
        else:
            return selfrom

    def includetagsbtn_clicked(self, btn):
        self.includetags = self.select_tags('Использовать только метки:',
            self.includetags,
            self.includetagstxt,
            self.INCLUDE_ANY)

    def excludetagsbtn_clicked(self, btn):
        self.excludetags = self.select_tags('Исключать метки:',
            self.excludetags,
            self.excludetagstxt,
            self.EXCLUDE_NOTHING)

    def main(self):
        Gtk.main()


def main():
    MainWnd(process_cmdline()).main()

    return 0


if __name__ == '__main__':
    sys.exit(main())
