#!/usr/bin/python3
# -*- coding: utf-8 -*-

from gtktools import *
from gi.repository import Gtk, Gdk, GObject, Pango
import random


REVISION = 20201109


class CheckListBox():
    __COL_CHECK, __COL_TEXT, __COL_USER_DATA = range(3)

    DEF_COLUMNS = 4
    DEF_ITEM_PADDING = 1
    DEF_ITEM_SPACING = 2

    BUTTONS_NONE, BUTTONS_RIGHT, BUTTONS_BOTTOM = range(3)

    def __toggled(self, crt, path):
        itr = self.checkstore.get_iter(path)

        checked = not self.checkstore.get_value(itr, self.__COL_CHECK)
        self.checkstore.set_value(itr, self.__COL_CHECK, checked)

        v = self.checkstore.get_value(itr, self.__COL_USER_DATA)
        if checked:
            self.selection.add(v)
        else:
            self.selection.remove(v)

    def __init__(self, buttonspos=BUTTONS_NONE):
        """buttonspos - расположение панели кнопок"""

        self.selection = set()

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

        crtx = Gtk.CellRendererText()
        crtx.set_alignment(0, 0)
        crtx.props.ellipsize = Pango.EllipsizeMode.END
        self.checklist.pack_start(crtx, True)
        self.checklist.add_attribute(crtx, 'text', self.__COL_TEXT)

        self.checklist.props.cell_area.add_focus_sibling(crtg, crtx)
        self.checklist.set_tooltip_column(self.__COL_TEXT)

        self.checklist.set_item_orientation(Gtk.Orientation.HORIZONTAL)
        #self.checklist.set_activate_on_single_click(True)

        self.scwindow = Gtk.ScrolledWindow()
        self.scwindow.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.scwindow.set_shadow_type(Gtk.ShadowType.IN)
        self.scwindow.add(self.checklist)

        if buttonspos == self.BUTTONS_BOTTOM:
            self.container = Gtk.VBox()
            buttonbox = Gtk.HBox()
        elif buttonspos == self.BUTTONS_RIGHT:
            self.container = Gtk.HBox()
            buttonbox = Gtk.VBox()
        else:
            self.container = self.scwindow
            buttonbox = None

        if buttonbox:
            self.container.pack_start(self.scwindow, True, True, 0)
            self.container.pack_end(buttonbox, False, False, 0)

            def addbtn(iconname, tooltip, sighandler, boolfunc):
                btn = Gtk.ToolButton.new(Gtk.Image.new_from_icon_name(iconname, Gtk.IconSize.MENU))
                btn.set_tooltip_text(tooltip)
                btn.connect('clicked', sighandler, boolfunc)
                buttonbox.pack_start(btn, False, False, 0)

            addbtn('checkbox-checked-symbolic', 'Включить все', self.__check_all, lambda b: True)
            addbtn('checkbox-symbolic', 'Сбросить все', self.__check_all, lambda b: False)
            addbtn('checkbox-mixed-symbolic', 'Переключить все', self.__check_all, lambda b: not b)

    def __check_all(self, btn, boolfunc):
        def fe_func(model, path, liter):
            b = boolfunc(model.get_value(liter, self.__COL_CHECK))
            v = model.get_value(liter, self.__COL_USER_DATA)

            if b:
                self.selection.add(v)

            model.set_value(liter, self.__COL_CHECK, b)

            return False

        self.selection.clear()
        self.checklist.set_model(None)
        self.checkstore.foreach(fe_func)
        self.checklist.set_model(self.checkstore)

    def clear(self):
        self.checkstore.clear()
        self.selection.clear()

    def append(self, check, text, data=None):
        self.checkstore.append((check, text, data))
        if check:
            self.selection.add(data)


def __test_checklistbox():
    def __destroy(widget):
        Gtk.main_quit()

    def __test_btn_clicked(btn):
        print(clb.selection)

    window = Gtk.Window()
    window.set_title('Тест CheckListBox')
    window.connect('destroy', __destroy)

    window.set_size_request(640, 240)

    rootvbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, WIDGET_SPACING)
    rootvbox.set_border_width(WIDGET_SPACING)
    window.add(rootvbox)


    clb = CheckListBox(CheckListBox.BUTTONS_BOTTOM)
    rootvbox.pack_start(clb.container, True, True, 0)

    demolist = ('one', 'two', 'three', 'four', 'five', 'six', 'seven')

    for ix, s in enumerate(demolist):
        clb.append(bool(random.randrange(2)), s, ix)

    hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, WIDGET_SPACING)
    rootvbox.pack_end(hbox, False, False, 0)

    btn = Gtk.Button.new_with_label('Test')
    hbox.pack_start(btn, False, False, 0)

    btn.connect('clicked', __test_btn_clicked)

    window.show_all()

    Gtk.main()


if __name__ == '__main__':
    print('[test of %s]' % __file__)

    __test_checklistbox()
