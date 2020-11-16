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

from gi.repository import Gtk, GdkPixbuf
from gi.repository.GdkPixbuf import Pixbuf
from gi.repository.GLib import markup_escape_text

from gtkchecklistbox import CheckListBox

import sys
import os.path
from shutil import which
from subprocess import Popen

from colorsys import rgb_to_hls
from math import sqrt

from inkavail import *
from inkrandom import RandomInkChooser


class MainWnd():
    PAGE_STAT, PAGE_CHOICE, PAGE_AVG_COLOR = range(3)

    INCLUDE_ANY = 'любые'
    EXCLUDE_NOTHING = 'никаких'

    LENS_SRC_CX = 17
    LENS_SRC_CY = LENS_SRC_CX
    LENS_OX = int(LENS_SRC_CX / 2)
    LENS_OY = int(LENS_SRC_CY / 2)
    LENS_SCALE = 8
    LENS_CX = LENS_SRC_CX * LENS_SCALE
    LENS_CY = LENS_SRC_CY * LENS_SCALE
    LENS_FILL = 0xc0c0c0ff

    MAX_COLOR_SAMPLES = 32

    SAMPLE_COL_VALUE, SAMPLE_COL_HINT, SAMPLE_COL_PIX = range(3)

    COPY_RGB, COPY_HEX, COPY_HLS = range(3)

    def wnd_destroy(self, widget):
        Gtk.main_quit()

    def __init__(self, fname):
        #
        self.emacs = which('emacs')
        self.emacsProcess = None

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

        #
        # страница статистики
        #
        self.totalstatlstore, self.totalstatview = get_ui_widgets(uibldr,
            'totalstatlstore', 'totalstatview')

        self.detailstatststore, self.detailstatsview, detailstatswnd = get_ui_widgets(uibldr,
            'detailstatststore detailstatsview detailstatswnd')

        # костылинг
        detailstatswnd.set_min_content_height(WIDGET_BASE_HEIGHT * 24)

        self.openorgfiledlg = uibldr.get_object('openorgfiledlg')

        # грязный хакЪ из-за ошибки в Glade 3.22.2, криво генерирующей элементы меню со значками
        mnuFile = uibldr.get_object('mnuFile')
        img = Gtk.Image.new_from_icon_name('open-menu-symbolic', Gtk.IconSize.MENU)
        mnuFile.add(img)

        #
        # страница случайного выбора чернил
        #
        self.randominkname, self.randominktags, self.randominkdesc, self.randominkavail = get_ui_widgets(uibldr,
            'randominkname randominktags randominkdesc randominkavail')
        self.randominkdescbuf = self.randominkdesc.get_buffer()

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
        # страница подбора среднего цвета
        #
        self.btnImageFile = uibldr.get_object('btnImageFile')
        self.btnImageFile.set_current_folder(os.path.abspath('.'))

        self.swImgView, self.imgView, self.ebImgView,\
        self.labCursorRGBX, self.imgLens, self.imgCursorColor = get_ui_widgets(uibldr,
            'swImgView', 'imgView', 'ebImgView',
            'labCursorRGBX', 'imgLens', 'imgCursorColor')

        self.pixbuf = None
        self.pixbufPixels = None
        self.pixbufChannels = 0
        self.pixbufRowStride = 0
        self.pixbufCX = 0
        self.pixbufCY = 0

        self.imgViewOX = 0
        self.imgViewOY = 0

        self.ebImgView.add_events(Gdk.EventMask.BUTTON_PRESS_MASK\
            | Gdk.EventMask.POINTER_MOTION_MASK\
            | Gdk.EventMask.LEAVE_NOTIFY_MASK)

        self.lensPixbuf = Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, self.LENS_CX, self.LENS_CY)
        self.lensPixbuf.fill(self.LENS_FILL)
        self.imgLens.set_from_pixbuf(self.lensPixbuf)

        #
        _, self.samplePixbufSize, _ = Gtk.IconSize.lookup(Gtk.IconSize.MENU)

        swSamples, self.ivSamples, self.lstoreSamples, self.labNSamples,\
        self.btnSampleRemove = get_ui_widgets(uibldr,
            'swSamples', 'ivSamples', 'lstoreSamples', 'labNSamples',
            'btnSampleRemove')
        self.itrSelectedSample = None

        swSamples.set_min_content_height(WIDGET_BASE_HEIGHT * 6)

        swSamples.set_size_request(WIDGET_BASE_WIDTH * 24, -1)

        #
        self.cursorColorPixbuf = Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, self.samplePixbufSize, self.samplePixbufSize)
        self.cursorColorPixbuf.fill(self.LENS_FILL)
        self.imgCursorColor.set_from_pixbuf(self.cursorColorPixbuf)

        #
        self.averageColorPixbuf = Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, self.samplePixbufSize, self.samplePixbufSize)
        self.averageColorPixbuf.fill(self.LENS_FILL)

        self.imgAverageColor, self.labAverageRGBX, self.btnCopy = get_ui_widgets(uibldr,
            'imgAverageColor','labAverageRGBX','btnCopy')

        self.imgAverageColor.set_from_pixbuf(self.averageColorPixbuf)

        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)

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

    def load_image(self, fname):
        tmppbuf = Pixbuf.new_from_file(fname)

        self.pixbufCX = tmppbuf.get_width()
        self.pixbufCY = tmppbuf.get_height()

        # создаём новый, строго заданного формата, мало ли что там загрузилось, м.б. вообще SVG
        self.pixbuf = Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, self.pixbufCX, self.pixbufCY)
        tmppbuf.copy_area(0, 0, self.pixbufCX, self.pixbufCY,
            self.pixbuf, 0, 0)

        self.pixbufPixels = self.pixbuf.get_pixels()
        self.pixbufChannels = self.pixbuf.get_n_channels()
        self.pixbufRowStride = self.pixbuf.get_rowstride()

        self.swImgView.set_max_content_width(self.pixbufCX)
        self.swImgView.set_max_content_height(self.pixbufCY)

        self.imgView.set_from_pixbuf(self.pixbuf)

        #
        self.lstoreSamples.clear()
        self.update_sample_count()

    def update_sample_count(self):
        self.labNSamples.set_text('%d (of %d)' % (self.lstoreSamples.iter_n_children(), self.MAX_COLOR_SAMPLES))

    def btnImageFile_file_set(self, fcbtn):
        fname = fcbtn.get_filename()

        self.load_image(fname)

    def mnuAverageColor_activate(self, mi):
        self.pages.set_current_page(self.PAGE_AVG_COLOR)
        self.btnImageFile.grab_focus()

    class ColorValue():
        # строим велосипед, т.к. Gdk.RGBA с какого-то чорта уродуется внутри Gtk.ListStore

        #__slots__ = 'r', 'g', 'b'

        def __init__(self, r, g, b):
            self.r = r
            self.g = g
            self.b = b

        def __eq__(self, other):
            return (self.r == other.r) and (self.g == other.g) and (self.b == other.b)

        @staticmethod
        def get_int_value(r, g, b):
            """Возвращает 32-битное значение вида 0xRRGGBBAA,
            которое можно скормить Pixbuf.fill()."""

            return (r << 24) | (g << 16) | (b << 8) | 0xff

        def __int__(self):
            return self.get_int_value(self.r, self.g, self.b)

        def __repr__(self):
            return '%s(r=%d, g=%d, b=%d)' % (self.__class__.__name__,
                self.r, self.g, self.b)

        def get_values(self):
            return (self.r, self.g, self.b)

        @staticmethod
        def get_hex_value(r, g, b):
            return '#%.2x%.2x%.2x' % (r, g, b)

        def to_hex(self):
            return self.get_hex_value(self.r, self.g, self.b)

        def to_hls(self):
            return rgb_to_hls(self.r, self.g, self.b)

    def color_sample_find_itr(self, v):
        itr = self.lstoreSamples.get_iter_first()

        while itr is not None:
            if v == self.lstoreSamples.get_value(itr, self.SAMPLE_COL_VALUE):
                return itr

            itr = self.lstoreSamples.iter_next(itr)

    def color_sample_add(self, x, y):
        r, g, b = self.get_pixbuf_pixel(x, y)

        colorv = self.ColorValue(r, g, b)

        itr = self.color_sample_find_itr(colorv)

        if (itr is None) and (self.lstoreSamples.iter_n_children() < self.MAX_COLOR_SAMPLES):
            pbuf = Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, self.samplePixbufSize, self.samplePixbufSize)
            pbuf.fill(int(colorv))

            itr = self.lstoreSamples.append((colorv,
                'R=%d, G=%d, B=%d (%s)' % (*colorv.get_values(), colorv.to_hex()),
                pbuf))

            self.ivSamples.select_path(self.lstoreSamples.get_path(itr))

            self.update_sample_count()
            self.compute_average_color()

    def compute_average_color(self):
        ra = 0.0
        ga = 0.0
        ba = 0.0
        nc = 0

        itr = self.lstoreSamples.get_iter_first()

        while itr is not None:
            colorv = self.lstoreSamples.get_value(itr, self.SAMPLE_COL_VALUE)

            ra += colorv.r * colorv.r
            ga += colorv.g * colorv.g
            ba += colorv.b * colorv.b

            nc += 1
            itr = self.lstoreSamples.iter_next(itr)

        colorv = self.ColorValue(int(sqrt(ra / nc)), int(sqrt(ga / nc)), int(sqrt(ba / nc)))

        self.averageColorPixbuf.fill(int(colorv))
        self.imgAverageColor.set_from_pixbuf(self.averageColorPixbuf)

        self.labAverageRGBX.set_text('%s' % colorv.to_hex())

    def btnSampleRemove_clicked(self, btn):
        if self.itrSelectedSample:
            self.lstoreSamples.remove(self.itrSelectedSample)
            self.compute_average_color()

    def ivSamples_selection_changed(self, iv):
        sel = iv.get_selected_items()
        if sel:
            self.itrSelectedSample = self.lstoreSamples.get_iter(sel[0])
        else:
            self.itrSelectedSample = None

        self.btnSampleRemove.set_sensitive(self.itrSelectedSample is not None)

    def imgView_size_allocate(self, wgt, r):
        """Коррекция координат Gtk.Image, т.к. размер его окна
        может быть больше физического размера изображения"""

        if r.width > self.pixbufCX:
            self.imgViewOX = (r.width - self.pixbufCX) // 2
        else:
            self.imgViewOX = 0

        if r.height > self.pixbufCY:
            self.imgViewOY = (r.height - self.pixbufCY) // 2
        else:
            self.imgViewOY = 0

    def ebImgView_button_press_event(self, wgt, event):
        if (event.button == 1) and (event.type == Gdk.EventType._2BUTTON_PRESS):
            self.color_sample_add(int(event.x) - self.imgViewOX, int(event.y) - self.imgViewOY)

            return True

    def get_pixbuf_pixel(self, x, y):
        pix = x * self.pixbufChannels + y * self.pixbufRowStride

        return (self.pixbufPixels[pix],
                self.pixbufPixels[pix + 1],
                self.pixbufPixels[pix + 2])

    def motion_event(self, x, y):
        self.lensPixbuf.fill(self.LENS_FILL)

        x = int(x) - self.imgViewOX
        y = int(y) - self.imgViewOY

        if (self.pixbuf is None) or (x < 0) or (x >= self.pixbufCX) or (y < 0) or (y >= self.pixbufCY):
            rgbx = '-'
            cursorColor = self.LENS_FILL
        else:
            pixel = self.get_pixbuf_pixel(x, y)

            cursorColor = self.ColorValue.get_int_value(*pixel)

            rgbx = self.ColorValue.get_hex_value(*pixel)

            sx = x - self.LENS_OX
            sy = y - self.LENS_OY
            cx = self.LENS_SRC_CX
            cy = self.LENS_SRC_CY
            dx = 0
            dy = 0

            if sx < 0:
                dx = -sx
                cx += sx
                sx = 0

            if sy < 0:
                dy = -sy
                cy += sy
                sy = 0

            tx = self.pixbufCX - sx - cx
            if tx < 0:
                cx += tx

            ty = self.pixbufCY - sy - cy
            if ty < 0:
                cy += ty

            if cx > 0 and cy > 0:
                region = self.pixbuf.new_subpixbuf(sx, sy, cx, cy)

                region.scale(self.lensPixbuf,
                    dx * self.LENS_SCALE, dy * self.LENS_SCALE, cx * self.LENS_SCALE, cy * self.LENS_SCALE,
                    0, 0,
                    self.LENS_SCALE, self.LENS_SCALE,
                    GdkPixbuf.InterpType.NEAREST)

        self.cursorColorPixbuf.fill(cursorColor)
        self.imgCursorColor.set_from_pixbuf(self.cursorColorPixbuf)
        self.imgLens.set_from_pixbuf(self.lensPixbuf)

        self.labCursorRGBX.set_text(rgbx)

    def ebImgView_leave_notify_event(self, wgt, event):
        self.motion_event(-1, -1)

        return True

    def ebImgView_motion_notify_event(self, wgt, event):
        self.motion_event(event.x, event.y)

        return True

    def btnCopy_clicked(self, btn):
        self.clipboard.set_text(self.labAverageRGBX.get_text(), -1)

    def main(self):
        Gtk.main()


def main():
    MainWnd(process_cmdline()).main()

    return 0


if __name__ == '__main__':
    sys.exit(main())
