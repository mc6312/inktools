#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" inktools.py

    Copyright 2020-2021 MC-6312 (http://github.com/mc6312)

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

from inktoolscfg import *
from inkavail import *
from inkrandom import RandomInkChooser


class MainWnd():
    DARK_THEME = True # потом м.б. сделать юзерскую настройку

    INCLUDE_ANY = 'любые'
    EXCLUDE_NOTHING = 'никаких'

    LENS_SRC_CX = 17
    LENS_SRC_CY = LENS_SRC_CX
    LENS_OX = int(LENS_SRC_CX / 2)
    LENS_OY = int(LENS_SRC_CY / 2)
    LENS_SCALE = 9
    LENS_CX = LENS_SRC_CX * LENS_SCALE
    LENS_CY = LENS_SRC_CY * LENS_SCALE

    SAMPLE_FILL_LIGHT = 0xc0c0c0ff
    SAMPLE_FILL_DARK = 0x202020ff

    MAX_COLOR_SAMPLES = 32

    DET_COL_INK, DET_COL_LABEL,\
    DET_COL_AVAIL, DET_COL_UNAVAIL, DET_COL_WANTED, DET_COL_UNWANTED,\
    DET_COL_COLOR, DET_COL_HINT = range(8)

    SAMPLE_COL_VALUE, SAMPLE_COL_HINT, SAMPLE_COL_PIX = range(3)

    COPY_RGB, COPY_HEX, COPY_HLS = range(3)

    def wnd_destroy(self, widget):
        Gtk.main_quit()

    def before_exit(self):
        self.cfg.save()

    def wnd_delete_event(self, wnd, event):
        self.before_exit()

    def wnd_configure_event(self, wnd, event):
        """Сменились размер/положение окна"""

        self.cfg.mainWindow.wnd_configure_event(wnd, event)

    def wnd_state_event(self, widget, event):
        """Сменилось состояние окна"""

        self.cfg.mainWindow.wnd_state_event(widget, event)

    def load_window_state(self):
        """Загрузка и установка размера и положения окна"""

        self.cfg.mainWindow.set_window_state(self.window)

    def mnuFileQuit_activate(self, mi):
        self.before_exit()
        self.wnd_destroy(mi)

    def __init__(self):
        #
        self.emacs = which('emacs')
        self.emacsProcess = None

        self.cfg = Config()

        self.cursorSamplers = (('rbtnCursorPixel', self.get_pixbuf_pixel_color),
                ('rbtnCursorBoxIntenseColor', self.get_pixbuf_intense_color))

        self.cfg.maxPixelSamplerMode = len(self.cursorSamplers) - 1
        self.cfg.load()

        resldr = get_resource_loader()
        uibldr = get_gtk_builder(resldr, 'inktools.ui')

        Gtk.Settings.get_default().set_property('gtk-application-prefer-dark-theme',
            self.DARK_THEME)

        self.sampleFillColor = self.SAMPLE_FILL_DARK if self.DARK_THEME else self.SAMPLE_FILL_LIGHT

        self.db = None
        self.rndchooser = None
        self.stats = None

        # для выбора в случайном выбираторе
        self.includetags = set()
        self.excludetags = set()

        __LOGO = 'inktools.svg'
        #
        # очень важное окно
        #
        self.aboutDialog = uibldr.get_object('aboutDialog')

        logoSize = WIDGET_BASE_HEIGHT * 10
        self.aboutDialog.set_logo(resldr.load_pixbuf(__LOGO, logoSize, logoSize))
        self.aboutDialog.set_program_name(TITLE)
        self.aboutDialog.set_version(TITLE_VERSION)
        self.aboutDialog.set_copyright(COPYRIGHT)
        self.aboutDialog.set_website(URL)
        self.aboutDialog.set_website_label(URL)

        #
        # основное окно
        #
        self.window = uibldr.get_object('inkavailwnd')
        icon = resldr.load_pixbuf_icon_size(__LOGO, Gtk.IconSize.DIALOG, 'computer')
        self.window.set_icon(icon)

        self.headerbar = uibldr.get_object('headerbar')

        self.headerbar.set_title(TITLE_VERSION)

        #
        self.pages, self.pageStatistics, self.pageChooser, self.pageSampler = get_ui_widgets(uibldr,
            'pages', 'pageStatistics', 'pageChooser', 'pageSampler')

        _, self.samplePixbufSize, _ = Gtk.IconSize.lookup(Gtk.IconSize.MENU)

        #
        # страница статистики
        #
        self.nocoloricon = resldr.load_pixbuf_icon_size(
            'nocolor-dark.svg' if self.DARK_THEME else 'nocolor.svg',
            Gtk.IconSize.MENU,
            'dialog-question-symbolic')

        self.totalstatlstore, self.totalstatview = get_ui_widgets(uibldr,
            'totalstatlstore', 'totalstatview')

        self.detailstats = TreeViewShell.new_from_uibuilder(uibldr, 'detailstatsview')
        detailstatswnd = uibldr.get_object('detailstatswnd')

        # костылинг
        detailstatswnd.set_min_content_height(WIDGET_BASE_HEIGHT * 24)

        self.openorgfiledlg = uibldr.get_object('openorgfiledlg')

        #
        # главное меню
        #

        # грязный хакЪ из-за ошибки в Glade 3.22.2, криво генерирующей элементы меню со значками
        # пока это всё оторву - пущай будет человеческое меню, а не гномье
        #mnuFile = uibldr.get_object('mnuFile')
        #img = Gtk.Image.new_from_icon_name('open-menu-symbolic', Gtk.IconSize.MENU)
        #mnuFile.add(img)

        self.mnuFileOpenRecent = uibldr.get_object('mnuFileOpenRecent')

        #
        # страница случайного выбора чернил
        #
        self.randominkname, self.randominktags, self.randominkdesc,\
        self.randominkavail, self.randominkstatus,\
        self.randominkcolorimg, self.randominkcolordesc, self.randominkmaincolor,\
        self.randominkusagecnt = get_ui_widgets(uibldr,
            'randominkname', 'randominktags', 'randominkdesc',
            'randominkavail', 'randominkstatus', 'randominkcolorimg',
            'randominkcolordesc', 'randominkmaincolor', 'randominkusagecnt')
        self.randominkdescbuf = self.randominkdesc.get_buffer()

        uibldr.get_object('randominkusagesw').set_size_request(-1, WIDGET_BASE_HEIGHT * 6)

        self.randominkusageview = TreeViewShell.new_from_uibuilder(uibldr, 'randominkusagetv')
        self.randominkusageview.sortColumn = 0

        self.includetagstxt, self.excludetagstxt, self.tagchooserdlg = get_ui_widgets(uibldr,
            'includetagstxt', 'excludetagstxt', 'tagchooserdlg')

        self.randominkColorPixbuf = Pixbuf.new(GdkPixbuf.Colorspace.RGB,
            False, 8, self.samplePixbufSize, self.samplePixbufSize)

        self.tagchecklistbox = CheckListBox(selectionbuttons=True)
        # костыль
        # потому что set_min_content_width с какого-то хрена не работает
        self.tagchecklistbox.scwindow.set_size_request(WIDGET_BASE_WIDTH * 80, WIDGET_BASE_HEIGHT * 10)
        #self.tagchecklistbox.scwindow.set_min_content_width(WIDGET_BASE_WIDTH * 90)
        #self.tagchecklistbox.scwindow.set_min_content_height(WIDGET_BASE_HEIGHT * 16)

        taglistvbox = self.tagchooserdlg.get_content_area()
        taglistvbox.pack_start(self.tagchecklistbox, True, True, 0)

        self.chosenInk = None

        #
        # страница подбора среднего цвета
        #
        self.btnImageFile = uibldr.get_object('btnImageFile')
        self.btnImageFile.set_current_folder(self.cfg.imageSampleDirectory)

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

        #
        # курсор цветовыбиралки
        #
        self.pixbufCursorImgView = resldr.load_pixbuf('cursor.png', None, None)
        self.cursorImgViewOX = 7
        self.cursorImgViewOY = 7

        # будут присвоены потом, когда ebImgView заимеет Gdk.Window
        self.cursorOutOfImgView = None
        self.cursorImgView = None

        self.ebImgView.add_events(Gdk.EventMask.BUTTON_PRESS_MASK\
            | Gdk.EventMask.POINTER_MOTION_MASK\
            | Gdk.EventMask.LEAVE_NOTIFY_MASK)

        self.lensPixbuf = Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, self.LENS_CX, self.LENS_CY)
        self.lensPixbuf.fill(self.sampleFillColor)
        self.imgLens.set_from_pixbuf(self.lensPixbuf)

        #
        swSamples, self.ivSamples, self.lstoreSamples, self.labNSamples,\
        self.btnSampleRemove = get_ui_widgets(uibldr,
            'swSamples', 'ivSamples', 'lstoreSamples', 'labNSamples',
            'btnSampleRemove')
        self.itrSelectedSample = None

        self.cursorSampler = self.get_pixbuf_pixel_color

        for ix, (rbtnn, sampler) in enumerate(self.cursorSamplers):
            #
            rbtn = uibldr.get_object(rbtnn)
            if ix == self.cfg.pixelSamplerMode:
                rbtn.set_active(True)

            rbtn.connect('toggled', self.rbtnCursorSamplerMode_toggled, ix)

        self.cursorSampler = self.cursorSamplers[self.cfg.pixelSamplerMode][-1]

        self.swImgView.set_min_content_width(WIDGET_BASE_WIDTH * 48)

        swSamples.set_min_content_height(WIDGET_BASE_HEIGHT * 6)
        swSamples.set_size_request(WIDGET_BASE_WIDTH * 24, -1)

        #
        self.cursorColorPixbuf = Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, self.samplePixbufSize, self.samplePixbufSize)
        self.cursorColorPixbuf.fill(self.sampleFillColor)

        self.imgCursorColor.set_from_pixbuf(self.nocoloricon)

        #
        self.averageColorPixbuf = Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, self.samplePixbufSize, self.samplePixbufSize)
        self.averageColorPixbuf.fill(self.sampleFillColor)

        self.imgAverageColor, self.labAverageRGBX, self.btnCopy = get_ui_widgets(uibldr,
            'imgAverageColor','labAverageRGBX','btnCopy')

        self.imgAverageColor.set_from_pixbuf(self.averageColorPixbuf)

        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)

        #
        self.window.show_all()
        self.load_window_state()
        self.update_recent_files_menu()

        uibldr.connect_signals(self)

        self.load_db()

    def update_recent_files_menu(self):
        if not self.cfg.recentFiles:
            self.mnuFileOpenRecent.set_submenu()
        else:
            mnu = Gtk.Menu.new()
            mnu.set_reserve_toggle_size(False)

            for ix, rfn in enumerate(self.cfg.recentFiles):
                # сокращаем отображаемое имя файла, длину пока приколотим гвоздями
                #TODO когда-нибудь сделать сокращение отображаемого в меню имени файла по человечески
                lrfn = len(rfn)
                if lrfn > 40:
                    disprfn = '%s...%s' % (rfn[:3], rfn[lrfn - 34:])
                else:
                    disprfn = rfn

                mi = Gtk.MenuItem.new_with_label(disprfn)
                mi.connect('activate', self.file_open_recent, ix)
                mnu.append(mi)

            mnu.show_all()

            self.mnuFileOpenRecent.set_submenu(mnu)

    def file_open_recent(self, wgt, ix):
        fname = self.cfg.recentFiles[ix]

        # проверяем наличие файла обязательно, т.к. в списке недавних
        # могут быть уже удалённые файлы или лежащие на внешних
        # неподключённых носителях
        # при этом метод file_open_filename() проверку производить
        # не должен, т.к. в первую очередь расчитан на вызов после
        # диалога выбора файла, который несуществующего файла не вернёт.
        # кроме того, сообщение об недоступном файле _здесь_ должно
        # отличаться от просто "нету файла"

        if not os.path.exists(fname):
            msg_dialog(self.window, TITLE,
                'Файл "%s" отсутствует или недоступен' % fname)
        else:
            self.cfg.databaseFileName = fname
            self.load_db()

    def mnuFileAbout_activate(self, mi):
        self.aboutDialog.show()
        self.aboutDialog.run()
        self.aboutDialog.hide()

    def rbtnCursorSamplerMode_toggled(self, rbtn, samplerIx):
        if rbtn.get_active():
            self.cursorSampler = self.cursorSamplers[samplerIx][-1]
            self.cfg.pixelSamplerMode = samplerIx

    def load_db(self):
        self.totalstatview.set_model(None)
        self.totalstatlstore.clear()

        self.detailstats.view.set_model(None)
        self.detailstats.store.clear()

        expand = []

        def __bool_s(b, clr=None):
            st = '√' if clr is None else '<span color="%s"><b>√</b></span>' % clr
            return st if b else ''

        CTODO = '#fd0'
        CNODO = '#c00'
        CDONE = '#0f0'

        try:
            self.db = load_ink_db(self.cfg.databaseFileName)
            self.stats = get_ink_stats(self.db)
            self.rndchooser = None

            # статистика
            if self.stats:
                dfname = os.path.split(self.cfg.databaseFileName)[-1]

                #
                # общая статистика
                #
                totals = self.stats.get_total_result_table()

                for row in totals:
                    self.totalstatlstore.append(row)

                #
                # детали
                #
                for tagstat in self.stats.tagStats:
                    itr = self.detailstats.store.append(None,
                            (None, tagstat.title, '', '', '', '', None, None))

                    expand.append(self.detailstats.store.get_path(itr))

                    _items = tagstat.stats.items()

                    # мелкий костылинг: сортироваться должны только списки,
                    # полученные обработкой директив TAGSTATS

                    if tagstat.issortable:
                        # порядок сортировки: название метки, наличие
                        # на кой чорт питонщики сделали key вместо cmp?
                        # в случае cmp не пришлось бы тратить память на
                        # значение временного ключа сортировки
                        # и фрагментировать кучу
                        def __group_key_f(r):
                            return '%5d%s' % (r[1].available,
                                              self.stats.get_tag_display_name(r[0]).lower())

                        _items = sorted(_items, key=__group_key_f, reverse=True)

                    for tag, nfo in _items:
                        row = (None, self.stats.get_tag_display_name(tag),
                            *nfo.counter_strs(), None,
                            None)

                        subitr = self.detailstats.store.append(itr, row)

                        # конкретные марки чернил сортируем уже по названию в алфавитном порядке
                        for ink in sorted(nfo.inks, key=lambda i: i.text.lower()):
                            if ink.color:
                                pbuf = Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, self.samplePixbufSize, self.samplePixbufSize)
                                pbuf.fill(int(ColorValue.get_rgb32_value(ink.color)))
                            else:
                                pbuf = self.nocoloricon

                            # 'название', 'отсортированный список человекочитаемых меток', 'описание', 'наличие'
                            _inkname, _inktags, _inkdesc, _inkavail = self.stats.get_ink_description(ink)

                            hint = ['<b>%s</b>' % markup_escape_text(_inkname)]

                            if ink.color:
                                hint.append('Цвет: <span color="#%.6x">██</span> %s' % (ink.color,
                                    markup_escape_text(ColorValue.new_from_rgb24(ink.color).get_description())))

                            if _inkdesc:
                                hint.append(markup_escape_text(_inkdesc))

                            if _inkavail:
                                hint.append('В наличии: %s' % markup_escape_text(_inkavail))

                            if ink.done == False:
                                hint.append('Запланирована покупка этих чернил')

                            if ink.missing:
                                hint.append('Отсутствуют данные: %s' % self.stats.get_ink_missing_data_str(ink))

                            bunwanted = ink.done is None
                            self.detailstats.store.append(subitr,
                                    (ink,
                                    ink.text,
                                    # avail
                                    __bool_s(ink.avail, CDONE),
                                    # unavail
                                    __bool_s(not ink.avail, None if bunwanted else CTODO),
                                    # wanted
                                    __bool_s(ink.done == False, CTODO), # прямое сравнение, т.к. иначе None будет воспринято тоже как False
                                    # unwanted
                                    __bool_s(bunwanted, CNODO),
                                    pbuf,
                                    '\n\n'.join(hint)))

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

            self.openorgfiledlg.select_filename(self.cfg.databaseFileName)
            self.headerbar.set_subtitle(dfname)

            self.cfg.add_recent_file(self.cfg.databaseFileName)
            self.update_recent_files_menu()

        finally:
            self.detailstats.view.set_model(self.detailstats.store)

            for path in expand:
                self.detailstats.view.expand_row(path, False)

            self.totalstatview.set_model(self.totalstatlstore)

        self.choose_random_ink()

    def detailstatsview_row_activated(self, tv, path, col):
        ink = self.detailstats.store.get_value(self.detailstats.store.get_iter(path),
            self.DET_COL_INK)

        if ink:
            self.show_ink(ink, True)

    def show_ink(self, ink, switchpage):
        inknamet = '...'
        inktagst = '-'
        inkdesct = ''
        inkavailt = '-'
        inkstatust = '-'
        inkcolordesc = '-' # тут когда-нибудь будет человекочитаемое описание цвета
        inkcolor = None
        inkmaincolor = '-'
        inkusagecnt = '...'

        self.chosenInk = ink

        self.randominkusageview.refresh_begin()

        if not ink:
            inknamet = 'ничего подходящего не нашлось'
        else:
            inkName, inkTags, inkDescription, inkAvailability = self.stats.get_ink_description(ink)

            inknamet = inkName
            inktagst = markup_escape_text(inkTags) if inkTags else '-'
            inkdesct = inkDescription
            inkavailt = markup_escape_text(inkAvailability)

            if ink.done is None:
                inkstatust = 'не нужны'
            elif ink.done:
                inkstatust = 'испытаны'
            else:
                inkstatust = 'планируется покупка'

            if ink.color:
                inkcolor = ColorValue.get_rgb32_value(ink.color)
                inkcolordesc = ColorValue.new_from_rgb24(ink.color).get_description()

            if ink.maincolor:
                inkmaincolor = self.stats.tagNames.get(ink.maincolor, ink.maincolor)

            dnow = datetime.datetime.now().date()

            inkusagecnt = 'заправок: %d' % len(ink.usage)

            for unfo in ink.usage:
                _dd = dnow - unfo.date

                self.randominkusageview.store.append((str(unfo.date),
                    'сегодня' if _dd.days <= 1 else '%d дн. назад' % _dd.days,
                    unfo.comment))

        self.randominkusageview.refresh_end()

        self.randominkname.set_text(inknamet)
        self.randominktags.set_markup(inktagst)
        self.randominkdescbuf.set_text(inkdesct)
        self.randominkavail.set_markup(inkavailt)
        self.randominkstatus.set_text(inkstatust)
        self.randominkcolordesc.set_text(inkcolordesc)
        self.randominkmaincolor.set_text(inkmaincolor)

        self.randominkusagecnt.set_text(inkusagecnt)

        if inkcolor is None:
            self.randominkcolorimg.set_from_pixbuf(self.nocoloricon)
        else:
            self.randominkColorPixbuf.fill(inkcolor)
            self.randominkcolorimg.set_from_pixbuf(self.randominkColorPixbuf)

        if switchpage:
            self.pages.set_visible_child(self.pageChooser)

    def choose_random_ink(self):
        if self.rndchooser is not None:
            self.rndchooser.filter_inks(self.excludetags, self.includetags)

            ink = self.rndchooser.choice()

            self.show_ink(ink, False)

    def randomchbtn_clicked(self, btn):
        self.choose_random_ink()

    def openeditbutton_clicked(self, btn):
        self.start_editor_on_chosen_ink()

    def mnuEditChosenInk_activate(self, mi):
        self.pages.set_visible_child(self.pageChooser)
        self.start_editor_on_chosen_ink()

    def mnuRandomChoice_activate(self, wgt):
        self.choose_random_ink()
        self.pages.set_visible_child(self.pageChooser)

    def mnuInkNameCopy_activate(self, wgt):
        vc = self.pages.get_visible_child()
        ink = None

        if vc == self.pageStatistics:
            itr = self.detailstats.get_selected_iter()
            if itr:
                ink = self.detailstats.store.get_value(itr,
                    self.DET_COL_INK)

        elif vc == self.pageChooser:
            ink = self.chosenInk

        if ink:
            self.clipboard.set_text(ink.text, -1)

    def select_load_db(self):
        self.openorgfiledlg.set_filename(self.cfg.databaseFileName)

        self.openorgfiledlg.show_all()
        r = self.openorgfiledlg.run()
        self.openorgfiledlg.hide()

        if r == Gtk.ResponseType.OK:
            fname = self.openorgfiledlg.get_filename()

            if fname != self.cfg.databaseFileName:
                self.cfg.databaseFileName = fname
                self.load_db()

            self.pages.set_visible_child(self.pageStatistics)

    def mnuFileOpen_activate(self, mi):
        self.select_load_db()

    def mnuFileReload_activate(self, mi):
        if not self.cfg.databaseFileName:
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

    def start_editor_on_chosen_ink(self):
        if self.chosenInk:
            self.start_editor(self.chosenInk.line)

    def start_editor(self, gotoline=-1):
        def __msg(what):
            msg_dialog(self.window,
                       TITLE,
                       what)

        if not self.cfg.databaseFileName:
            __msg('Файл БД не выбран. Сначала выберите его...')
        elif not self.emacs:
            __msg('Для редактирования БД требуется редактор Emacs')
        elif self.__emacs_is_running():
            __msg('Редактор БД уже работает')
        else:
            try:
                cmd = [self.emacs, '--no-desktop', '--no-splash']

                if gotoline >= 0:
                    cmd.append('+%d' % gotoline)

                cmd.append(self.cfg.databaseFileName)

                self.emacsProcess = Popen(cmd)
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

    def load_sample_image(self, fname):
        """Загрузка изображения с образцом чернил в определитель цвета."""

        tmppbuf = Pixbuf.new_from_file(fname)

        self.pixbufCX = tmppbuf.get_width()
        self.pixbufCY = tmppbuf.get_height()

        # создаём новый, строго заданного формата, мало ли что там загрузилось
        self.pixbuf = Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, self.pixbufCX, self.pixbufCY)

        # на случай наличия альфа-канала в исходном изображении
        self.pixbuf.fill(0xffffffff)

        tmppbuf.composite(self.pixbuf,
            0, 0, self.pixbufCX, self.pixbufCY,
            0, 0, 1.0, 1.0,
            GdkPixbuf.InterpType.TILES, 255);

        self.pixbufPixels = self.pixbuf.get_pixels()
        self.pixbufChannels = self.pixbuf.get_n_channels()
        self.pixbufRowStride = self.pixbuf.get_rowstride()

        #self.swImgView.set_max_content_width(self.pixbufCX)
        #self.swImgView.set_max_content_height(self.pixbufCY)

        self.imgView.set_from_pixbuf(self.pixbuf)

        self.swImgView.get_hadjustment().set_value(0)
        self.swImgView.get_vadjustment().set_value(0)

        #
        self.lstoreSamples.clear()
        self.update_sample_count()
        self.compute_average_color()

    def update_sample_count(self):
        self.labNSamples.set_text('%d (of %d)' % (self.lstoreSamples.iter_n_children(), self.MAX_COLOR_SAMPLES))

    def btnImageFile_file_set(self, fcbtn):
        fname = fcbtn.get_filename()

        self.cfg.imageSampleDirectory = os.path.split(fname)[0]

        self.load_sample_image(fname)

    def mnuAverageColor_activate(self, mi):
        self.pages.set_visible_child(self.pageSampler)
        self.btnImageFile.grab_focus()

    def color_sample_find_itr(self, v):
        itr = self.lstoreSamples.get_iter_first()

        while itr is not None:
            if v == self.lstoreSamples.get_value(itr, self.SAMPLE_COL_VALUE):
                return itr

            itr = self.lstoreSamples.iter_next(itr)

    def color_sample_add(self, x, y):
        colorv = self.cursorSampler(x, y)

        if colorv is None:
            return

        itr = self.color_sample_find_itr(colorv)

        if (itr is None) and (self.lstoreSamples.iter_n_children() < self.MAX_COLOR_SAMPLES):
            pbuf = Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, self.samplePixbufSize, self.samplePixbufSize)
            pbuf.fill(int(colorv))

            itr = self.lstoreSamples.append((colorv,
                'R=%d, G=%d, B=%d (%s)' % (*colorv.get_values(), colorv.hexv),
                pbuf))

            self.ivSamples.select_path(self.lstoreSamples.get_path(itr))

            self.update_sample_count()
            self.compute_average_color()

    def compute_average_color(self):
        colorv = ColorValue(0, 0, 0)

        itr = self.lstoreSamples.get_iter_first()

        while itr is not None:
            colorv.avg_color_add(self.lstoreSamples.get_value(itr, self.SAMPLE_COL_VALUE))

            itr = self.lstoreSamples.iter_next(itr)

        colorv = colorv.avg_color_get()

        if colorv:
            self.averageColorPixbuf.fill(int(colorv))
            pb = self.averageColorPixbuf
            ch = colorv.hexv
        else:
            pb = self.nocoloricon
            ch = '-'

        self.imgAverageColor.set_from_pixbuf(pb)

        self.labAverageRGBX.set_text('%s' % ch)

    def color_sample_remove(self):
        if self.itrSelectedSample:
            self.lstoreSamples.remove(self.itrSelectedSample)
            self.compute_average_color()

    def btnSampleRemove_clicked(self, btn):
        self.color_sample_remove()

    def btnSampleRemoveAll_clicked(self, btn):
        self.lstoreSamples.clear()
        self.compute_average_color()

    def ivSamples_selection_changed(self, iv):
        sel = iv.get_selected_items()
        if sel:
            self.itrSelectedSample = self.lstoreSamples.get_iter(sel[0])
        else:
            self.itrSelectedSample = None

        self.btnSampleRemove.set_sensitive(self.itrSelectedSample is not None)

    def ivSamples_item_activated(self, iv, path):
        self.color_sample_remove()

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

    def get_pixbuf_pixel_color(self, x, y):
        """Получение значения цвета для точки из self.pixbuf
        по координатам x, y.
        Возвращает экземпляр ColorValue, если координаты находятся
        внутри границ self.pixel, иначе None."""

        if (self.pixbuf is None) or (x < 0) or (x >= self.pixbufCX) or (y < 0) or (y >= self.pixbufCY):
            return None

        pix = x * self.pixbufChannels + y * self.pixbufRowStride

        return ColorValue(self.pixbufPixels[pix],
                self.pixbufPixels[pix + 1],
                self.pixbufPixels[pix + 2])

    def __scan_pixel_area(self, x, y, cmpf):
        """Просматривает область 7х7 точек вокруг указанных координат.
        Возвращает экземпляр ColorValue для точки, наиболее
        подходящей под условие. Если область за пределами изображения,
        возвращает None.

        x, y    - координаты курсора;
        cmpf    - функция;
                  получает два экземпляра ColorValue,
                  возвращает булевское значение, результат сравнения
                  цветов."""

        # размер области пока приколочен гвоздями

        retc = None

        for ox in range(x - 3, x + 4):
            for oy in range(y - 3, y + 4):
                c = self.get_pixbuf_pixel_color(ox, oy)

                if c is not None:
                    if (retc is None) or (cmpf(retc, c)):
                        retc = c
                        retc = c

        return retc

    def get_pixbuf_intense_color(self, x, y):
        """Возвращает значение самого тёмного и насыщенного цвета из
        области 7х7 в виде экземпляра ColorValue.
        Если область за пределами границ self.pixbuf, возвращает None."""

        def __is_intense(clr, otherclr):
            return (clr.s < otherclr.s) and (clr.l > otherclr.l)

        return self.__scan_pixel_area(x, y, __is_intense)

    def motion_event(self, x, y):
        self.lensPixbuf.fill(self.sampleFillColor)

        x = int(x) - self.imgViewOX
        y = int(y) - self.imgViewOY

        pixelc = self.cursorSampler(x, y)

        if pixelc is None:
            rgbx = '-'
            samplePixbuf = self.nocoloricon
            cursor = None if (x < 0) and (y < 0) else self.cursorOutOfImgView
        else:
            rgbx = pixelc.hexv
            cursor = self.cursorImgView

            self.cursorColorPixbuf.fill(int(pixelc))
            samplePixbuf = self.cursorColorPixbuf

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

        self.imgview_set_cursor(cursor)

        self.imgCursorColor.set_from_pixbuf(samplePixbuf)
        self.imgLens.set_from_pixbuf(self.lensPixbuf)

        self.labCursorRGBX.set_text(rgbx)

    def ebImgView_realize(self, wgt):
        disp = self.ebImgView.get_window().get_display()

        if not self.cursorImgView:
            self.cursorOutOfImgView = Gdk.Cursor.new_for_display(disp, Gdk.CursorType.X_CURSOR)

            self.cursorImgView = Gdk.Cursor.new_from_pixbuf(disp,
                self.pixbufCursorImgView,
                self.cursorImgViewOX, self.cursorImgViewOY)

    def imgview_set_cursor(self, cursor):
        self.ebImgView.get_window().set_cursor(cursor)

    def ebImgView_enter_notify_event(self, wgt, event):
        self.motion_event(event.x, event.y)

        return True

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
    MainWnd().main()

    return 0


if __name__ == '__main__':
    sys.exit(main())
