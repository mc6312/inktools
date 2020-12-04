#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" inktoolscfg.py

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

from gtktools import *

from gi.repository import Gtk, Gdk

import json
import os, os.path, sys


JSON_ENCODING = 'utf-8'


class WindowState():
    MAXIMIZED = 'maximized'

    class WinPos():
        """Класс для хранения положения и размеров окна."""

        __slots__ = 'x', 'y', 'width', 'height'

        def __init__(self, x=0, y=0, width=0, height=0):
            self.x = x
            self.y = y
            self.width = width
            self.height = height

        def todict(self):
            d = dict()

            for vname in self.__slots__:
                v = getattr(self, vname)
                if v:
                    d[vname] = v

            return d

        def fromdict(self, d):
            for vname in self.__slots__:
                setattr(self, vname, d[vname] if vname in d else 0)

        def __repr__(self):
            # для отладки

            return '%s(x=%s, y=%s, width=%s, height=%s)' % (self.__class__.__name__,
                self.x, self.y, self.width, self.height)

    def __init__(self):
        self.sizepos = self.WinPos()
        self.oldsizepos = self.WinPos()
        self.maximized = False

        self.__lockcnt = 0

    def wnd_configure_event(self, wnd, event):
        """Сменились размер/положение окна"""

        if self.__lockcnt:
            return

        # реальные размеры и положение - в event неправильные!
        ww, wh = wnd.get_size()
        wx, wy = wnd.get_position()

        # сохраняем старое положение для борьбы с поведением GTK,
        # который вызывает configure-event с "максимизированным"
        # размером перед вызовом window-state-event
        # авось, поможет...
        self.oldsizepos = self.sizepos
        #self.sizepos = self.WinPos(event.x, event.y, event.width, event.height)
        self.sizepos = self.WinPos(wx, wy, ww, wh)

    def wnd_state_event(self, widget, event):
        """Сменилось состояние окна"""

        if self.__lockcnt:
            return

        self.maximized = bool(event.new_window_state & Gdk.WindowState.MAXIMIZED)

        #if self.maximized:
        #    self.sizepos = self.oldsizepos

        #print('wnd_state_event (maximized=%s)' % self.maximized)

    def __lock(self):
        self.__lockcnt += 1

    def __unlock(self):
        if self.__lockcnt > 0:
            self.__lockcnt -= 1

    def set_window_state(self, window):
        """Установка положения/размера окна"""

        self.__lock()

        #print('set_window_state: %s' % self.sizepos)

        if self.sizepos.x is not None:
            window.move(self.sizepos.x, self.sizepos.y)

            # все равно GTK не даст меньше допустимого съёжить
            window.resize(self.sizepos.width, self.sizepos.height)

        if self.maximized:
            window.maximize()

        flush_gtk_events() # грязный хакЪ, дабы окно смогло поменять размер

        self.__unlock()

    def fromdict(self, d):
        self.sizepos.fromdict(d)

        self.maximized = d[self.MAXIMIZED] if self.MAXIMIZED in d else False

    def todict(self):
        d = dict()

        if self.maximized:
            d[self.MAXIMIZED] = self.maximized

        d.update(self.sizepos.todict())

        return d

    def __repr__(self):
        # для отладки

        return '%s(sizepos=%s, oldsizepos=%s, maximized=%s)' % (self.__class__.__name__,
            self.sizepos, self.oldsizepos, self.maximized)


class Config():
    MAINWINDOW = 'mainwindow'

    SAMPLEDIR = 'image_sample_directory'
    DBFNAME = 'database_file_name'
    SAMPLERMODE = 'pixel_sampler_mode'

    RECENTFILES = 'recentfiles'

    CFGFN = 'settings.json'
    CFGAPP = 'inktools'

    MAX_RECENT_FILES = 16 # ибо нефиг

    def __init__(self):
        #
        # положение и состояние окон
        #
        self.mainWindow = WindowState()

        #
        # общие настройки
        #
        self.imageSampleDirectory = os.path.abspath('.')

        self.defaultDBFileName = os.path.join(os.path.split(os.path.abspath(sys.argv[0]))[0], 'inks.org')
        self.databaseFileName = self.defaultDBFileName

        # значение должно быть установлено снаружи перед вызовом Config.load()
        self.maxPixelSamplerMode = 1

        self.pixelSamplerMode = 0

        # ранее открывавшиеся файлы (список строк)
        self.recentFiles = []

        # определяем каталог для настроек
        # или принудительно создаём, если его ещё нет

        # некоторый костылинг вместо xdg.BaseDirectory, которого есть не для всех ОС
        self.configDir = os.path.join(os.path.expanduser('~'), '.config', self.CFGAPP)
        if not os.path.exists(self.configDir):
            os.makedirs(self.configDir)

        self.configPath = os.path.join(self.configDir, self.CFGFN)
        # вот сейчас самого файла может ещё не быть!

    def load(self):
        E_SETTINGS = 'Ошибка в файле настроек "%s": %%s' % self.configPath

        def __dict_get(d, pname, ptype, fallback):
            v = d.get(pname, fallback)

            if not isinstance(v, ptype):
                raise EnvironmentError(E_SETTINGS % ('тип параметра "%s" должен быть %s' % (pname, ptype.__name__)))

            return v

        if os.path.exists(self.configPath):
            with open(self.configPath, 'r', encoding=JSON_ENCODING) as f:
                d = json.load(f)

                #
                if self.MAINWINDOW in d:
                    self.mainWindow.fromdict(d[self.MAINWINDOW])

                self.imageSampleDirectory = d.get(self.SAMPLEDIR, os.path.abspath('.'))

                self.databaseFileName = d.get(self.DBFNAME, self.defaultDBFileName)

                self.pixelSamplerMode = __dict_get(d, self.SAMPLERMODE, int, 0)
                if self.pixelSamplerMode < 0:
                    self.pixelSamplerMode = 0
                elif self.pixelSamplerMode > self.maxPixelSamplerMode:
                    self.pixelSamplerMode = self.maxPixelSamplerMode

                #
                # список открывавшихся файлов
                #
                rfl = __dict_get(d, self.RECENTFILES, list, [])

                self.recentFiles.clear()

                for ix, rfn in enumerate(rfl, 1):
                    if not isinstance(rfn, str):
                        raise TypeError(E_SETTINGS % ('недопустимый тип элемента #%d списка "%s"' % (ix, self.RECENTFILES)))

                    rfn = rfn.strip()
                    if not rfn:
                        continue

                    # проверку на наличие файлов - пока нафиг: а вдруг оне на флэшке невоткнутой?
                    #if not os.path.exists(rfn):
                    #    continue

                    self.add_recent_file(rfn)

        # минимальная обработка командной строки
        if len(sys.argv) >= 2:
            # путь к БД, указанный в командной строке, имеет приоритет перед настройками из файла
            self.databaseFileName = os.path.abspath(os.path.expanduser(sys.argv[1]))

    def add_recent_file(self, fname):
        try:
            self.recentFiles.index(fname)
        except ValueError:
            self.recentFiles.append(fname)

            if len(self.recentFiles) > self.MAX_RECENT_FILES:
                del self.recentFiles[0]

    def save(self):
        tmpd = {self.MAINWINDOW:self.mainWindow.todict(),
            self.SAMPLEDIR:self.imageSampleDirectory,
            self.DBFNAME:self.databaseFileName,
            self.SAMPLERMODE:self.pixelSamplerMode}

        if self.recentFiles:
            tmpd[self.RECENTFILES] = self.recentFiles

        with open(self.configPath, 'w+', encoding=JSON_ENCODING) as f:
            json.dump(tmpd, f, ensure_ascii=False, indent='  ')

    def __repr__(self):
        # для отладки

        return '%s(configDir="%s", configPath="%s", mainWindow=%s, imageSampleDirectory="%s", databaseFileName="%s", pixelSamplerMode=%d, recentFiles=%s)' % (
            self.__class__.__name__,
            self.configDir, self.configPath, self.mainWindow,
            self.imageSampleDirectory, self.databaseFileName,
            self.pixelSamplerMode,
            self.recentFiles)


def main(args):
    return 0


if __name__ == '__main__':
    print('[debugging %s]' % __file__)

    cfg = Config()
    cfg.load()
    #cfg.save()

    print(cfg)
