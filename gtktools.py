#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" gtktools.py

    Набор обвязок и костылей к GTK, общий для типовых гуёв.

    Copyright 2018-2021 MC-6312 (http://github.com/mc6312)

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


# для обвязок GTK
from gi import require_version as gi_require_version
gi_require_version('Gtk', '3.0')
# если сей модуль, gtktools, указать первым перед прочими связанными
# с GTK модулями - не придётся из оттудова дёргать gi_require_version()
from gi.repository import Gtk, Gdk, GObject, GLib, Pango, Gio
from gi.repository.GdkPixbuf import Pixbuf


# для *ResourceLoader
import zipfile
from sys import stderr, argv
import os.path


REVISION = 2021042400


def get_widget_base_units():
    """Получение базовых значений, которые можно использовать для расчета
    отступов между виджетами и т.п., дабы несчастного пользователя
    не вывернуло от пионерского вида гуя.
    Значения считаем на основе размера шрифта по умолчанию, так как
    прицепиться больше не к чему.
    Возвращает кортеж из двух элементов - средней ширины символа
    и высоты строки. Оба значения в пикселах."""

    pangoContext = Gdk.pango_context_get()
    metrics = pangoContext.get_metrics(pangoContext.get_font_description(),
        None)

    return (int(metrics.get_approximate_char_width() / Pango.SCALE),
            int(metrics.get_height() / Pango.SCALE))


WIDGET_BASE_WIDTH, WIDGET_BASE_HEIGHT = get_widget_base_units()

# обычный интервал между виджетами (напр. внутри Gtk.Box)
WIDGET_SPACING = WIDGET_BASE_WIDTH // 2
# меньше делать будет бессмысленно
if WIDGET_SPACING < 4:
    WIDGET_SPACING = 4

# расширенный интервал - для разделения групп виджетов там,
# где Gtk.Separator не смотрится
WIDE_WIDGET_SPACING = WIDGET_SPACING * 3


def load_system_icon(name, size, pixelsize=False, fallback=None, symbolic=False):
    """Возвращает Pixbuf для "системной" (из установленной темы)
    иконки с именем name и размером size.

    name        - стока с именем иконки в системной теме;
    size        - размер иконки (Gtk.IconSize.* или целое);
    pixelsize   - булевское значение;
                  если True - size д.б. целым числом, размером в пикселях;
    fallback    - None или строка с именем иконки на случай отсутствия
                  в системной теме иконки с именем name;
    symbolic    - искать "плоскую" иконку.

    Возвращает экземпляр Gtk.Pixbuf
    (или None, если подходящей иконки нет)."""

    if not pixelsize:
        size = Gtk.IconSize.lookup(size)[1]

    theme = Gtk.IconTheme.get_default()

    flags = Gtk.IconLookupFlags.FORCE_SIZE

    if symbolic:
        flags |= Gtk.IconLookupFlags.FORCE_SYMBOLIC

    icon = theme.lookup_icon(name, size, flags)

    if icon is None:
        if fallback:
            icon = theme.lookup_icon(fallback, size, flags)

    return icon.load_icon() if icon is not None else None


#
# "общие" иконки
#
MENU_ICON_SIZE_PIXELS =  Gtk.IconSize.lookup(Gtk.IconSize.MENU)[1]


def get_ui_widgets(builder, *names):
    """Получение списка указанных виджетов.
    builder     - экземпляр класса Gtk.Builder,
    names       - строки с имёнами виджетов,
                  в виде 'имя', 'имя1', 'имяN'
                  и/или ('имя', 'имя1', 'имяN')
                  и/или 'имя имя1 имяN'.
    Возвращает список экземпляров Gtk.Widget и т.п."""

    widgets = []

    def __parse_params(plst):
        for param in plst:
            if isinstance(param, list) or isinstance(param, tuple):
                __parse_params(param)
            elif isinstance(param, str):
                param = param.split(None)

                if len(param) > 1:
                    __parse_params(param)
                else:
                    wgt = builder.get_object(param[0])
                    if wgt is None:
                        raise KeyError('get_ui_widgets(): экземпляр Gtk.Builder не содержит виджет с именем "%s"' % param[0])

                    widgets.append(wgt)
            else:
                raise ValueError('get_ui_widgets(): недопустимый тип элемента в списке имён виджетов')

    __parse_params(names)

    return widgets


class WidgetList(list):
    """Список экземпляров Gtk.Widget, позволяющий вытворять с собой всякое."""

    @classmethod
    def new_from_builder(cls, builder, *names):
        return cls(get_ui_widgets(builder, names))

    def set_sensitive(self, bsensitive):
        for widget in self:
            widget.set_sensitive(bsensitive)

    def set_visible(self, bvisible):
        for widget in self:
            widget.set_visible(bvisible)

    def set_style(self, css):
        """Задание стиля для виджетов widgets в формате CSS"""

        dbsp = Gtk.CssProvider()
        dbsp.load_from_data(css) # убейте гномосексуалистов кто-нибудь!

        for widget in self:
            dbsc = widget.get_style_context()
            dbsc.add_provider(dbsp, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


def set_widgets_sensitive(widgets, bsensitive):
    """Устанавливает значения свойства "sensitive" равным значению
    bsensitive для виджетов из списка widgets.
    Оставлено для совместимости, далее лучше использовать WidgetList."""

    for widget in widgets:
        widget.set_sensitive(bsensitive)


def set_widgets_visible(widgets, bvisible):
    """Устанавливает значения свойства "visible" равным значению
    bvisible для виджетов из списка widgets.
    Оставлено для совместимости, далее лучше использовать WidgetList."""

    for widget in widgets:
        widget.set_visible(bvisible)


def get_child_with_class(container, wantclass):
    """Ищет первый попавшийся виджет класса wantclass
    в виджете-контейнере container.

    Может пригодиться, когда нужно принудительно дёрнуть grab_focus()
    для какого-то составного виджета вроде Gtk.FileChooser, "внешний"
    контейнер которого не умеет принимать фокус ввода.

    Если чего найдет - возвращает ссылку на экземпляр, иначе возвращает
    None."""

    if not isinstance(container, Gtk.Container):
        return None

    children = container.get_children()

    if not children:
        return None

    for child in children:
        if isinstance(child, wantclass):
            return child

    # страдаем рекурсией только в том случае, если на текущем уровне
    # не нашлось ни одного подходящего виджета
    for child in children:
        r = get_child_with_class(child, wantclass)
        if r is not None:
            return r


def create_aligned_label(title, halign=0.0, valign=0.0):
    label = Gtk.Label.new(title)
    label.set_xalign(halign)
    label.set_yalign(valign)
    return label


def set_widget_style(css, *widgets):
    """Задание стиля для виджетов widgets в формате CSS.
    Оставлено для совместимости и для издевательств над
    отдельными виджетами.
    Для групп виджетов стоит использовать одноимённый
    метод класса WidgetList."""

    dbsp = Gtk.CssProvider()
    dbsp.load_from_data(css) # убейте гномосексуалистов кто-нибудь!

    for widget in widgets:
        dbsc = widget.get_style_context()
        dbsc.add_provider(dbsp, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


def msg_dialog(parentw, title, msg, msgtype=Gtk.MessageType.ERROR,
               buttons=Gtk.ButtonsType.OK, widgets=None,
               destructive_response=None,
               suggested_response=None,
               default_response=None):
    """Стандартное диалоговое окно с сообщением.

    Параметры:
        parentw - None или экземпляр Gtk.Window (окно, относительно
                  которого диалог д.б. модальным);
        title   - строка - заголовок;
        msg     - строка - текст сообщения (может содержать Pango Markup);
        msgtype - Gtk.MessageType.*;
        buttons - Gtk.ButtonsType.*;
        widgets - None или список экземпляров Gtk.Widget, добавляемых
                  в диалоговое окно;
        destructive_response    - None или Gtk.ResponseType.* для кнопки,
                  соответствующей деструктивному действию (напр. "YES"
                  для диалога "Удалить ...");
        suggested_response      - None или Gtk.ResponseType.* для кнопки,
                  соответствующей предпочитаемому действию;
        default_response        - None или Gtk.ResponseType.* для кнопки,
                  соответствующей действию по умолчанию (может совпадать
                  с destructive_response или default_response).

        Функция возвращает Gtk.ResponseType.*."""

    dlg = Gtk.MessageDialog(parent=parentw, message_type=msgtype, buttons=buttons,
        modal=True)

    dlg.set_title(title)
    dlg.set_markup(msg)

    if default_response is not None:
        dlg.set_default_response(default_response)

    def __btn_setup(response, cssclass):
        if response is not None:
            dlg.get_widget_for_response(response).get_style_context().add_class(cssclass)

    __btn_setup(destructive_response, 'destructive-action')
    __btn_setup(suggested_response, 'suggested-action')

    if widgets is not None:
        ca = dlg.get_message_area()

        for widget in widgets:
            ca.pack_start(widget, False, False, 0)

        ca.show_all()

    r = dlg.run()
    dlg.destroy()

    return r


def create_file_filter(name, patterns):
    """Создаёт экземпляр Gtk.FileFilter для Gtk.FileChooser*.

    name     - строка для отображения в комбобоксе выбора типа файлов,
    patterns - маски типов файлов, в виде строки, разделённой запятыми,
               или кортежа/списка строк (которые могут содержать
               несколько масок, разделённых запятыми)."""

    ffl = Gtk.FileFilter()
    ffl.set_name(name)

    def add_pattern_str(s):
        for pat in map(lambda v: v.strip(), s.split(',')):
            if pat:
                ffl.add_pattern(pat)

    if isinstance(patterns, str):
        add_pattern_str(patterns)
    elif isinstance(patterns, list) or isinstance(patterns, tuple):
        for pv in patterns:
            add_pattern_str(pv)

    return ffl


def get_gtk_builder(resldr, filename):
    """Возвращает экземпляр класса Gtk.Builder.
    resldr - экземпляр класса *ResourceLoader,
    filename - имя файла .ui.
    Функция оставлена для совместимости, следует использовать
    resldr.load_gtk_builder()."""

    return resldr.load_gtk_builder(filename)


def flush_gtk_events():
    """Даём GTK переварить все накопившиеся события"""

    while Gtk.events_pending():
        Gtk.main_iteration()


def get_resource_loader():
    """Возвращает экземпляр класса FileResourceLoader
    или ZipFileResourceLoader, в зависимости от того, как запущена
    программа - из обычного файла, или из архива ZIP."""

    # получаем путь к главному модулю (приложению)
    appFilePath = os.path.abspath(argv[0])

    # мы в жо... в зипе?
    appIsZIP = zipfile.is_zipfile(appFilePath)

    return ZipFileResourceLoader(appFilePath) if appIsZIP else FileResourceLoader(appFilePath);


class FileResourceLoader():
    """Загрузчик файлов ресурсов.
    Mожет использоваться при загрузке файлов иконок, .ui и т.п.

    Внимание! Методы этого класса в случае ошибок генерируют исключения."""

    def __init__(self, appFilePath):
        """Инициализация.

        appFilePath - путь к основному файлу (модулю) приложения."""

        self.appFilePath = appFilePath
        self.appDir = os.path.split(appFilePath)[0]

    def load(self, filename):
        """Загружает файл filename в память и возвращает в виде
        bytestring.

        filename - относительный путь к файлу."""

        filename = os.path.join(self.appDir, filename)

        if not os.path.exists(filename):
            raise ValueError('Файл "%s" не найден' % filename)

        try:
            self.error = None
            with open(filename, 'rb') as f:
                return f.read()
        except Exception as ex:
            # для более внятных сообщений
            self.error = 'Не удалось загрузить файл "%s" - %s' % (filename, str(ex))

    def load_bytes(self, filename):
        """Загружает файл filename в память и возвращает в виде
        экземпляра GLib.Bytes.

        filename - относительный путь к файлу."""

        return GLib.Bytes.new(self.load(filename))

    def load_memory_stream(self, filename):
        """Загружает файл в память и возвращает в виде экземпляра Gio.MemoryInputStream."""

        return Gio.MemoryInputStream.new_from_bytes(self.load_bytes(filename))

    @staticmethod
    def pixbuf_from_bytes(b, width, height):
        """Создаёт и возвращает экземпляр Gdk.Pixbuf.

        b       - экземпляр GLib.Bytes с данными в формате PNG/JPG/...,
        width,
        height  - целые, размеры изображения в пикселах, если нужен
                  определённый размер;
                  для загрузки "как есть" следует указывать значения
                  <=0 или None."""

        if isinstance(width, int) and width > 0:
            return Pixbuf.new_from_stream_at_scale(Gio.MemoryInputStream.new_from_bytes(b),
                    width, height, None)
        else:
            return Pixbuf.new_from_stream(Gio.MemoryInputStream.new_from_bytes(b), None)

    def load_pixbuf_icon_size(self, filename, size, fallback=None):
        """Делает то же, что load_pixbuf, но size - константа Gtk.IconSize.*"""

        size = Gtk.IconSize.lookup(size)[1]

        return self.load_pixbuf(filename, size, size, fallback)

    def load_pixbuf(self, filename, width, height, fallback=None):
        """Загружает файл в память и возвращает экземпляр Gdk.Pixbuf.

        filename        - имя файла (см. load_bytes),
        width, height   - целые, размеры изображения в пикселах, если нужен
                          определённый размер;
                          для загрузки "как есть" следует указывать значения
                          <=0 или None.
        fallback        - имя стандартной иконки, которая будет загружена,
                          если не удалось загрузить файл filename;
                          если fallback=None - генерируется исключение."""

        try:
            return self.pixbuf_from_bytes(self.load_bytes(filename),
                width, height)
        except Exception as ex:
            print('Can not load image "%s" - %s' % (filename, str(ex)), file=stderr)
            if fallback is None:
                raise ex
            else:
                print('Loading fallback image "%s"' % fallback, file=stderr)

                if not isinstance(height, int) or height <= 0:
                    # времянка!
                    height = Gtk.IconSize.lookup(Gtk.IconSize.MENU)[1]

                return Gtk.IconTheme.get_default().load_icon(fallback, height, Gtk.IconLookupFlags.FORCE_SIZE)

    def load_gtk_builder(self, filename):
        """Загружает в память и возвращает экземпляр класса Gtk.Builder.
        filename - имя файла .ui.
        При отсутствии файла и прочих ошибках генерируются исключения."""

        uistr = self.load(filename)
        return Gtk.Builder.new_from_string(str(uistr, 'utf-8'), -1)


class ZipFileResourceLoader(FileResourceLoader):
    """Загрузчик файлов ресурсов из архива ZIP.
    Архив - сам файл приложения в случае, когда он
    представляет собой python zip application."""

    def load(self, filename):
        """Аналогично FileResourceLoader.load(), загружает файл
        filename в память и возвращает в виде экземпляра bytestring.

        filename - путь к файлу внутри архива."""

        if not zipfile.is_zipfile(self.appFilePath):
            raise TypeError('Файл "%s" не является архивом ZIP' % self.appFilePath)

        with zipfile.ZipFile(self.appFilePath, allowZip64=True) as zfile:
            try:
                with zfile.open(filename, 'r') as f:
                    return f.read()
            except Exception as ex:
                raise Exception('Не удалось загрузить файл "%s" - %s' % (filename, str(ex)))


class TreeViewShell():
    """Обёртка для упрощения дёргания Gtk.TreeView"""

    def __init__(self, tv):
        """Параметры:
            tv      - экземпляр Gtk.TreeView.

        Поля:
            view        - экземпляр Gtk.TreeView;
            store       - экземпляр потомка Gtk.TreeModel;
            selection   - экземпляр Gtk.TreeSelection;
            widget      - экземпляр потомка Gtk.Widget,
                          который следует помещать в контейнер
                          при полностью динамическом создании UI.
            Внимание! Назначение прочих заданных в конструкторе полей
            может быть изменено в следующих версиях модуля."""

        self.view = tv
        self.store = tv.get_model()
        self.selection = tv.get_selection()

        self.widget = tv

        self.sortOrder = Gtk.SortType.ASCENDING
        self.sortColumn = -1

    class Cell():
        """Класс-хранилище параметров для создания Gtk.CellRenderer*"""

        def __init__(self, index, editable=False, expand=False, align=0.0, markup=False):
            """Параметры:
            index       - номер столбца в List|TreeStore,
            editable    - (булевское) запрет/разрешение редактирования ячейки,
            expand      - (булевское) фиксированная/автоматическая ширина,
            align       - (0.0..1.0) выравнивание содержимого ячейки,
            markup      - (булевское) для столбцов типа GObject.TYPE_STRING:
                          True - использовать Pango Markup при отображении столбца,
                          False - отображать как простой текст."""

            self.index = index
            self.editable = editable
            self.expand = expand
            self.align = align
            self.markup = markup

    class Column():
        """Класс-хранилище параметров для создания Gtk.TreeViewColumn."""

        def __init__(self, cells, title='', expand=False, tooltip=None):
            """Параметры:
            cells       - список или кортеж из как минимум одного экземпляра Cell,
            title       - отображаемое в заголовке название,
            expand      - (булевское) фиксированная/автоматическая ширина,
            tooltip     - если не None, то целое - индекс столбца в *Store,
                          который должен использоваться для отображения
                          tooltips (всплывающих подсказок);
                          если None - для подсказки будет использован
                          столбец index первого элемента cells."""

            self.cells = cells
            self.title = title
            self.expand = expand
            self.tooltip = tooltip if tooltip is not None else cells[0].index

    @classmethod
    def new(cls, tv):
        # сей метод - для единообразия
        return cls(tv)

    @classmethod
    def new_view(cls, coltypes, colparams, islist=True, withscroll=False):
        """Создаёт Gtk.TreeView, Gtk.ListStore|TreeStore и т.п. динамически.
        coltypes    - список или кортеж типов значений для Gtk.ListStore;
        cols        - список или кортеж параметров столбцов, где элементы -
                      экземпляры TreeViewer.Column;
        withscroll  - булевское значение, True, если нужно создать
                      экземпляр Gtk.ScrolledWindow и поместить
                      TreeView туда."""

        store = (Gtk.ListStore if islist else Gtk.TreeStore)(*coltypes)
        tv = Gtk.TreeView.new_with_model(store)

        tvsh = cls(tv)

        if withscroll:
            tvsh.scroll = Gtk.ScrolledWindow()
            tvsh.scroll.add(tv)

            tvsh.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            tvsh.scroll.set_overlay_scrolling(False)
            tvsh.scroll.set_shadow_type(Gtk.ShadowType.IN)

            tvsh.widget = tvsh.scroll

        ncols = len(coltypes)

        for colparam in colparams:
            col = Gtk.TreeViewColumn.new()
            #self.columns.append(col)

            for cix, cell in enumerate(colparam.cells, 1):
                if cell.index < 0 or cell.index >= ncols:
                    raise IndexError('%s.new_list(): Cell.index out of range' % cls.__class__.__name__)

                ctype = coltypes[cell.index]

                if ctype == GObject.TYPE_BOOLEAN:
                    crt = Gtk.CellRendererToggle()
                    crtpar = 'active'
                elif ctype == GObject.TYPE_STRING:
                    crt = Gtk.CellRendererText() #!!!
                    crt.props.xalign = cell.align

                    if cell.expand:
                        crt.props.ellipsize = Pango.EllipsizeMode.END
                    else:
                        crt.props.ellipsize = Pango.EllipsizeMode.NONE

                    crt.props.editable = cell.editable
                    crtpar = 'text' if not cell.markup else 'markup'
                elif ctype == Pixbuf:
                    crt = Gtk.CellRendererPixbuf()
                    crt.props.xalign = cell.align
                    crtpar = 'pixbuf'
                else:
                    raise ValueError('%s.new_list(): unsupported Gtk.%s column #%d data type' % (
                                     cls.__class__.__name__,
                                     store.__class__.__name__,
                                     cix))

                col.pack_start(crt, cell.expand)
                col.add_attribute(crt, crtpar, cell.index)

            tvsh.view.append_column(col)
            col.set_title(colparam.title)
            col.set_sizing(Gtk.TreeViewColumnSizing.GROW_ONLY)
            col.set_resizable(colparam.expand)
            col.set_expand(colparam.expand)
            #tvsh.colmap[col] = colparam.tooltip

        return tvsh

    @classmethod
    def new_from_uibuilder(cls, builder, widgetname):
        """Создаёт экземпляр TreeViewShell, запрашивая
        экземпляр Gtk.TreeView у builder (экземпляра класса Gtk.Builder)
        по имени виджета widgetname."""

        return cls(builder.get_object(widgetname))

    def get_iter_last(self, itr=None):
        """Возвращает Gtk.TreeIter последнего элемента на уровне itr,
        или None, если такового нет."""

        n = self.store.iter_n_children(None)
        if n > 0:
            return self.store.get_iter(Gtk.TreePath.new_from_indices([n - 1]))

    def get_selected_iter(self):
        """Возвращает Gtk.TreeIter первого выбранного элемента (если
        что-то выбрано) или None."""

        sel = self.selection.get_selected_rows()

        if sel is not None:
            rows = sel[1]
            if rows:
                return self.store.get_iter(rows[0])

    def find_iter(self, col, v, fromIter=None):
        """Рекурсивный поиск положения в Gtk.TreeModel.

        col         - номер столбца в TreeModel,
        v           - значение столбца, которое следует найти,
        fromIter    - None или Gtk.TreeIter:
                      начальное положение в TreeModel;
                      в случае None поиск идёт с первого элемента TreeModel.

        Возвращает Gtk.TreeIter для первого найденного значения,
        или None, если ничего не находит."""

        itr = self.store.iter_children(fromIter)
        while itr:
            if v == self.store.get_value(itr, col):
                return itr

            subitr = self.find_iter(col, v, itr)
            if subitr:
                return subitr

            itr = self.store.iter_next(itr)

    def select_iter(self, itr, col=None, edit=False):
        """Выбирает указанный элемент в дереве, указанный itr (экземпляром
        Gtk.TreeIter), при необходимости заставляет TreeView развернуть
        соответствующий уровень дерева.

        itr     - экземпляр Gtk.TreeIter;
        col     - None или Gtk.TreeViewColumn;
        edit    - булевское значение; если True, col is not None
                  и соотв. ячейка редактируемая - включает режим
                  редактирования ячейки."""

        path = self.store.get_path(itr)

        # иначе для неразвёрнутых ветвей строка вообще не будет подсвечена
        # странная особенность поведения TreeView
        self.view.expand_to_path(path)

        self.selection.select_path(path)
        self.view.set_cursor(path, col, edit)

    def enable_sorting(self, enable):
        """Разрешение/запрет сортировки treestore."""

        self.store.set_sort_column_id(
            self.sortColumn if (enable and self.sortColumn >= 0) else Gtk.TREE_SORTABLE_UNSORTED_SORT_COLUMN_ID,
            self.sortOrder)

    def refresh_begin(self):
        """Подготовка экземпляра TreeModel к заполнению данными:
        очистка, временный запрет сортировки.
        Вызывать перед полным обновлением."""

        self.view.set_model(None)
        self.enable_sorting(False)
        self.store.clear()

    def refresh_end(self):
        """Завершение заполнения данными."""

        self.enable_sorting(True)
        self.view.set_model(self.store)


def __debug_msgdlg():
    print(msg_dialog(None, 'Message dialog test', 'Delete anything?', buttons=Gtk.ButtonsType.YES_NO,
        destructive_response=Gtk.ResponseType.YES,
        suggested_response=Gtk.ResponseType.NO))


def __debug_load_icon():
    pbuf = load_system_icon('applications-internet',
        Gtk.IconSize.MENU,
        symbolic=True)

    print(pbuf)

def __debug_treeviewshell():
    tvsh = TreeViewShell.new_view(
        (GObject.TYPE_STRING, GObject.TYPE_STRING, GObject.TYPE_STRING,),
        (TreeViewShell.Column((TreeViewShell.Cell(0),), 'moo'),
         TreeViewShell.Column((TreeViewShell.Cell(1),
            TreeViewShell.Cell(2)), 'foo')))


if __name__ == '__main__':
    print('[debugging %s]' % __file__)

    #__debug_msgdlg()
    #__debug_load_icon()
    __debug_treeviewshell()

