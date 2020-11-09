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

import sys
import os.path
from shutil import which
from subprocess import run as subprocess_run

from inkavail import *
from inkrandom import RandomInkChooser


class MainWnd():
    PAGE_STAT, PAGE_CHOICE = range(2)

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

        self.detailstatststore, self.detailstatsview = get_ui_widgets(uibldr,
            'detailstatststore detailstatsview')

        self.openorgfiledlg = uibldr.get_object('openorgfiledlg')

        self.randominkname, self.randominktags, self.randominkdesc, self.randominkavail = get_ui_widgets(uibldr,
            'randominkname randominktags randominkdesc randominkavail')
        self.randominkdescbuf = self.randominkdesc.get_buffer()

        # грязный хакЪ из-за ошибки в Glade 3.22.2, криво генерирующей элементы меню со значками
        mnuFile = uibldr.get_object('mnuFile')
        img = Gtk.Image.new_from_icon_name('open-menu-symbolic', Gtk.IconSize.MENU)
        mnuFile.add(img)

        #
        self.includetagstxt, self.excludetagstxt, self.taglistpopover, self.taglistpopoverhdr = get_ui_widgets(uibldr,
            'includetagstxt', 'excludetagstxt', 'taglistpopover', 'taglistpopoverhdr')

        #
        mnuFileEdit = uibldr.get_object('mnuFileEdit')
        self.emacs = which('emacs')

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
            #TODO присобачить выбор меток
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

    def mnuFileOpen_activate(self, mi):
        self.openorgfiledlg.show_all()
        r = self.openorgfiledlg.run()
        self.openorgfiledlg.hide()

        if r == Gtk.ResponseType.OK:
            fname = self.openorgfiledlg.get_filename()

            if fname != self.dbfname:
                self.dbfname = fname
                self.load_db()

            self.pages.set_current_page(self.PAGE_STAT)

    def mnuFileEdit_activate(self, wgt):
        if not self.emacs:
            msg_dialog(self.window,
                       TITLE,
                       'Для редактирования БД требуется редактор Emacs')
        else:
            try:
                # чисто для подстраховки - один фиг GTK main loop залипнет
                # во время работы subprocess_run()
                self.window.set_sensitive(False)
                try:
                    flush_gtk_events()
                    p = subprocess_run([self.emacs, '--no-desktop', '--no-splash', self.dbfname])

                    if p.returncode != 0:
                        msg_dialog(self.window, TITLE, 'Редактор БД завершился с ошибкой.')
                    else:
                        self.load_ink_db(self.dbfname)
                finally:
                    self.window.set_sensitive(True)
            except Exception as ex:
                print('* %s' % str(ex), file=sys.stderr)
                msg_dialog(self.window, TITLE, 'Сбой запуска редактора БД')

    def select_tags(self, parentwidget, title):
        self.taglistpopoverhdr.set_text(title)
        self.taglistpopover.set_relative_to(parentwidget)
        self.taglistpopover.show()

    def taglistokbtn_clicked(self, btn):
        self.taglistpopover.hide()

    def taglistcancelbtn_clicked(self, btn):
        self.taglistpopover.hide()

    def includetagsbtn_clicked(self, btn):
        self.select_tags(btn, 'Использовать только метки:')

    def excludetagsbtn_clicked(self, btn):
        self.select_tags(btn, 'Исключать метки:')

    def main(self):
        Gtk.main()


def main():
    MainWnd(process_cmdline()).main()

    return 0


if __name__ == '__main__':
    sys.exit(main())
