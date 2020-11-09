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

from inkavail import *
from inkrandom import RandomInkChooser


class MainWnd():
    def wnd_destroy(self, widget):
        Gtk.main_quit()

    def __init__(self, fname):
        #
        resldr = get_resource_loader()
        uibldr = get_gtk_builder(resldr, 'inkavail.ui')

        self.dbfname = fname
        self.db = None
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
        self.totalstatlstore, self.totalstatview = get_ui_widgets(uibldr,
            ('totalstatlstore', 'totalstatview'))

        self.detailstatststore, self.detailstatsview = get_ui_widgets(uibldr,
            ('detailstatststore', 'detailstatsview'))

        self.srcfilebtn = uibldr.get_object('srcfilebtn')

        self.randominkname, self.randominkdesc, self.randominkavail = get_ui_widgets(uibldr,
            ('randominkname', 'randominkdesc', 'randominkavail'))

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

            else:
                dfname = ''

            self.srcfilebtn.select_filename(self.dbfname)
            self.headerbar.set_subtitle(dfname)


        finally:
            self.detailstatsview.set_model(self.detailstatststore)
            self.detailstatsview.expand_all()
            self.totalstatview.set_model(self.totalstatlstore)

        self.choose_random_ink()

    def srcfilebtn_file_set(self, fcbtn):
        fname = fcbtn.get_filename()

        if fname != self.dbfname:
            self.dbfname = fname
            self.load_db()

    def choose_random_ink(self):
        if self.stats is None:
            inknamet = '...'
            inkdesct = ''
            inkavailt = ''
        else:
            chooser = RandomInkChooser(self.stats)

            #TODO присобачить выбор меток
            ink = chooser.choice(set(), set()) #excludeTags, includeTags)
            if not ink:
                inkt = 'ничего подходящего не нашлось'
            else:
                inkName, inkTags, inkDescription, inkAvailability = chooser.get_ink_description(ink)

                inknamet = '<b>%s</b> (%s)' % (markup_escape_text(inkName),
                    markup_escape_text(inkTags))

                inkdesct = markup_escape_text(inkDescription)

                inkavailt = 'В наличии: %s' % markup_escape_text(inkAvailability)

        self.randominkname.set_markup(inknamet)
        self.randominkdesc.set_markup(inkdesct)
        self.randominkavail.set_markup(inkavailt)

    def randomchbtn_clicked(self, btn):
        self.choose_random_ink()

    def main(self):
        Gtk.main()


def main():
    MainWnd(process_cmdline()).main()

    return 0


if __name__ == '__main__':
    sys.exit(main())
