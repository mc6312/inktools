#!/usr/bin/python3
# -*- coding: utf-8 -*-

""" gtkchecklistbox.py

    Костыльно-велосипедный виджет GTK - список с чекбоксами.

    Copyright 2020 MC-6312 (http://github.com/mc6312)

    This module is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This module is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this module.  If not, see <http://www.gnu.org/licenses/>."""

from gtktools import *
from gi.repository import Gtk
import random


REVISION = 20201110


class CheckListBox(Gtk.Frame):
    """Составной виджет, содержащий Gtk.IconView с чекбоксами
    и, опционально, Gtk.Toolbar с кнопками группового изменения
    состояния чекбоксов.

    Большое "спасибо" разработчикам GTK, которые поленились сделать
    подобный виджет сами.

    Параметры, поля и методы (в дополнение к штатным Gtk.Frame):

    Параметры:
        selectionbuttons - булевское значение; если True - добавляется
            панель с кнопками переключения состояния выделения всех
            элементов списка.

    Поля (в дополнение к штатным Gtk.Box):
        checkstore  - экземпляр Gtk.ListStore;
        checklist   - экземпляр Gtk.IconView;
        toolbar     - экземпляр Gtk.Toolbar;
        scwindow    - экземпляр Gtk.ScrolledWindow, в котором размещен
                      checklist;
        box         - экземпляр Gtk.Box, в котором расположены
                      вышеперечисленные виджеты.

    Методы, в дополнение к штатным Gtk.Box (см. описания методов ниже):
        add_item                - добавление элемента в список;
        clear_items             - очистка списка элементов;
        get_selection           - получение списка выбора;
        get_selection_titles    - получение списка текстовых меток
                                  выбранных в checklist элементов;
        set_selection           - установка состояний чекбоксов."""

    __COL_CHECK, __COL_TEXT, __COL_USER_DATA = range(3)

    DEF_COLUMNS = 4
    DEF_ITEM_PADDING = 1
    DEF_ITEM_SPACING = 2

    def __toggled(self, crt, path):
        itr = self.checkstore.get_iter(path)

        checked = not self.checkstore.get_value(itr, self.__COL_CHECK)
        self.checkstore.set_value(itr, self.__COL_CHECK, checked)

    def __init__(self, *args, **kwargs):
        #
        # обработка "неродных" для Gtk.Frame параметров
        #
        def __get_param(name, defval):
            if name in kwargs:
                v = kwargs[name]
                # иначе Gtk.Frame будет лаяться на незнакомый параметр
                del kwargs[name]
            else:
                v = defval

            return v

        selectionbuttons = __get_param('selectionbuttons', False)
        orientation = __get_param('orientation', Gtk.Orientation.HORIZONTAL)

        super().__init__(*args, **kwargs)

        self.checkstore = Gtk.ListStore.new((GObject.TYPE_BOOLEAN, GObject.TYPE_STRING, object))

        self.checklist = Gtk.IconView.new_with_model(self.checkstore)
        self.checklist.set_columns(self.DEF_COLUMNS)
        self.checklist.props.item_padding = self.DEF_ITEM_PADDING
        self.checklist.props.column_spacing = self.DEF_ITEM_SPACING
        self.checklist.props.row_spacing = self.DEF_ITEM_SPACING
        self.checklist.set_tooltip_column(self.__COL_TEXT)

        crtg = Gtk.CellRendererToggle()
        crtg.set_alignment(0, 0)
        self.checklist.pack_start(crtg, False)
        self.checklist.add_attribute(crtg, 'active', self.__COL_CHECK)
        crtg.connect('toggled', self.__toggled)

        self.checklist.connect('item-activated', self.__toggled)

        crtx = Gtk.CellRendererText()
        crtx.set_alignment(0, 0)
        crtx.props.ellipsize = Pango.EllipsizeMode.END
        self.checklist.pack_start(crtx, True)
        self.checklist.add_attribute(crtx, 'text', self.__COL_TEXT)

        self.checklist.props.cell_area.add_focus_sibling(crtg, crtx)
        self.checklist.set_tooltip_column(self.__COL_TEXT)

        self.checklist.set_item_orientation(Gtk.Orientation.HORIZONTAL)
        #self.checklist.set_activate_on_single_click(True)

        self.box = Gtk.Box.new(orientation, 0)
        # spacing==0, т.к. тулбар должен быть вплотную к окну прокрутки
        self.add(self.box)

        self.scwindow = Gtk.ScrolledWindow()
        self.scwindow.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        #self.scwindow.set_shadow_type(Gtk.ShadowType.IN)
        self.scwindow.add(self.checklist)

        self.box.pack_start(self.scwindow, True, True, 0)

        if selectionbuttons:
            self.toolbar = Gtk.Toolbar()

            # ориентация тулбара "перпендикулярна" ориентации self.box!
            if orientation == Gtk.Orientation.VERTICAL:
                tbo = Gtk.Orientation.HORIZONTAL
            else:
                tbo = Gtk.Orientation.VERTICAL

            self.toolbar.set_orientation(tbo)

            self.toolbar.set_style(Gtk.ToolbarStyle.ICONS)
            self.toolbar.set_icon_size(Gtk.IconSize.MENU)
            self.toolbar.set_show_arrow(False)

            # а надо ли?
            self.box.pack_start(Gtk.Separator.new(tbo), False, False, 0)

            self.box.pack_end(self.toolbar, False, False, 0)

            def __addbtn(iconname, tooltip, sighandler, boolfunc):
                btn = Gtk.ToolButton.new(Gtk.Image.new_from_icon_name(iconname, Gtk.IconSize.MENU))
                btn.set_tooltip_text(tooltip)
                btn.connect('clicked', sighandler, boolfunc)
                self.toolbar.insert(btn, -1)

            __addbtn('checkbox-checked-symbolic', 'Включить все', self.__check_all, lambda b: True)
            __addbtn('checkbox-symbolic', 'Сбросить все', self.__check_all, lambda b: False)
            __addbtn('checkbox-mixed-symbolic', 'Переключить все', self.__check_all, lambda b: not b)

    def __check_all(self, btn, boolfunc):
        def __fe_func(model, path, liter):
            b = boolfunc(model.get_value(liter, self.__COL_CHECK))
            v = model.get_value(liter, self.__COL_USER_DATA)

            model.set_value(liter, self.__COL_CHECK, b)

            return False

        self.checklist.set_model(None)
        self.checkstore.foreach(__fe_func)
        self.checklist.set_model(self.checkstore)

    def clear_items(self):
        """Удаление всех элементов из спискa."""

        self.checkstore.clear()

    def add_item(self, check, text, data):
        """Добавление элемента в список.

        Параметры:
        check   - булевское значение: состояние чекбокса;
        text    - строка: текст метки чекбокса;
        data    - пользовательские данные;
                  значение этого параметра будет возвращено методом
                  get_selection()."""

        self.checkstore.append((check, text, data))

    def get_selection_titles(self, checked=True):
        """Возвращает список заголовков (текстовых меток)
        элементов списка, для которых значение чекбокса
        равно checked."""

        titles = []

        def __fe_func(model, path, liter):
            if model.get_value(liter, self.__COL_CHECK) == checked:
                titles.append(model.get_value(liter, self.__COL_TEXT))

            return False

        self.checkstore.foreach(__fe_func)

        return titles

    def get_selection(self, checked=True):
        """Возвращает список из экземпляров пользовательских данных
        для элементов списка, у которых значение чекбокса равно checked.
        Т.к. у разных элементов списка значения data могут совпадать,
        метод возвращает именно список, а не множество."""

        selection = []

        def __fe_func(model, path, liter):
            if model.get_value(liter, self.__COL_CHECK) == checked:
                selection.append(model.get_value(liter, self.__COL_USER_DATA))

            return False

        self.checkstore.foreach(__fe_func)

        return selection

    def set_selection(self, datalist):
        """Устанавливает значение чекбоксов для элементов списка.

        Параметры:
            datalist    - список, кортеж или множество значений
                          пользовательских данных
                          (см. описание add_item);
                          чекбоксы будут установлены для элементов
                          списка CheckListBox, значения data которых
                          совпадают со значениями из datalist.

        Т.к. значения полей data могут быть одинаковыми у нескольких
        элементов списка CheckListBox, чекбоксы будут включены у всех
        соответствующих элементов."""

        def __fe_func(model, path, liter):
            data = model.get_value(liter, self.__COL_USER_DATA)
            model.set_value(liter, self.__COL_CHECK, data in datalist)

            return False

        self.checkstore.foreach(__fe_func)


def __test_checklistbox():
    def __destroy(widget):
        Gtk.main_quit()

    window = Gtk.Window()
    window.set_title('Тест CheckListBox')
    window.connect('destroy', __destroy)

    window.set_size_request(640, 240)

    rootvbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, WIDGET_SPACING)
    rootvbox.set_border_width(WIDGET_SPACING)
    window.add(rootvbox)


    clb = CheckListBox(selectionbuttons=True)
    rootvbox.pack_start(clb, True, True, 0)

    __rb = lambda : bool(random.randrange(2))

    demolist = ((__rb(), 'one'), (__rb(), 'two'), (__rb(), 'three'),
        (__rb(), 'four'), (__rb(), 'five'), (__rb(), 'six'),
        (__rb(), 'seven'))

    selections = []

    for ix, (c, s) in enumerate(demolist):
        clb.add_item(c, s, ix)
        if c:
            selections.append(ix)

    selections = set(selections)

    hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, WIDGET_SPACING)
    rootvbox.pack_end(hbox, False, False, 0)

    def __btn_get_clicked(btn):
        print(clb.get_selection())
        print(clb.get_selection_titles(True))

    btn = Gtk.Button.new_with_label('Get selection')
    btn.connect('clicked', __btn_get_clicked)
    hbox.pack_start(btn, False, False, 0)

    def __btn_set_clicked(btn):
        clb.set_selection(selections)

    btn = Gtk.Button.new_with_label('Set selection')
    btn.connect('clicked', __btn_set_clicked)
    hbox.pack_start(btn, False, False, 0)

    window.show_all()

    Gtk.main()


if __name__ == '__main__':
    print('[test of %s]' % __file__)

    __test_checklistbox()
