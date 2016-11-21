#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# This file is part of nautilus-convert2ogg
#
# Copyright (C) 2012-2016 Lorenzo Carbonell
# lorenzo.carbonell.cerezo@gmail.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#
#
import gi
try:
    gi.require_version('Gtk', '3.0')
    gi.require_version('Nautilus', '3.0')
except Exception as e:
    print(e)
    exit(-1)
import os
import subprocess
import shlex
import tempfile
import shutil
from threading import Thread
from urllib import unquote_plus
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import GLib
from gi.repository import Nautilus as FileManager


EXTENSIONS_FROM = ['.mp3', '.wav', '.mp4', '.flv']
SEPARATOR = u'\u2015' * 10

_ = str


class IdleObject(GObject.GObject):
    """
    Override GObject.GObject to always emit signals in the main thread
    by emmitting on an idle handler
    """
    def __init__(self):
        GObject.GObject.__init__(self)

    def emit(self, *args):
        GLib.idle_add(GObject.GObject.emit, self, *args)


class DoItInBackground(IdleObject, Thread):
    __gsignals__ = {
        'started': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, ()),
        'ended': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, (bool,)),
        'done_one': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, ()),
    }

    def __init__(self, what_to_do, elements):
        IdleObject.__init__(self)
        Thread.__init__(self)
        self.what_to_do = what_to_do
        self.elements = elements
        self.stopit = False
        self.ok = True
        self.daemon = True

    def stop(self, *args):
        self.stopit = True

    def run(self):
        self.emit('started')
        try:
            for element in self.elements:
                if self.stopit is True:
                    self.ok = False
                    break
                self.what_to_do(element)
                self.emit('done_one')
        except Exception as e:
            self.ok = False
        self.emit('ended', self.ok)


class Progreso(Gtk.Dialog):
    __gsignals__ = {
        'i-want-stop': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, ()),
    }

    def __init__(self, title, parent, max_value):
        Gtk.Dialog.__init__(self, title, parent)
        self.set_position(Gtk.WindowPosition.CENTER_ALWAYS)
        self.set_size_request(330, 30)
        self.set_resizable(False)
        self.connect('destroy', self.close)
        # self.set_modal(True)
        vbox = Gtk.VBox(spacing=5)
        vbox.set_border_width(5)
        self.get_content_area().add(vbox)
        #
        frame1 = Gtk.Frame()
        vbox.pack_start(frame1, True, True, 0)
        table = Gtk.Table(2, 2, False)
        frame1.add(table)
        #
        self.label = Gtk.Label()
        table.attach(self.label, 0, 2, 0, 1,
                     xpadding=5,
                     ypadding=5,
                     xoptions=Gtk.AttachOptions.SHRINK,
                     yoptions=Gtk.AttachOptions.EXPAND)
        #
        self.progressbar = Gtk.ProgressBar()
        self.progressbar.set_size_request(300, 0)
        table.attach(self.progressbar, 0, 1, 1, 2,
                     xpadding=5,
                     ypadding=5,
                     xoptions=Gtk.AttachOptions.SHRINK,
                     yoptions=Gtk.AttachOptions.EXPAND)
        button_stop = Gtk.Button()
        button_stop.set_size_request(40, 40)
        button_stop.set_image(
            Gtk.Image.new_from_stock(Gtk.STOCK_STOP, Gtk.IconSize.BUTTON))
        button_stop.connect('clicked', self.on_button_stop_clicked)
        table.attach(button_stop, 1, 2, 1, 2,
                     xpadding=5,
                     ypadding=5,
                     xoptions=Gtk.AttachOptions.SHRINK)
        self.stop = False
        self.show_all()
        self.max_value = max_value
        self.value = 0.0

    def get_stop(self):
        return self.stop

    def on_button_stop_clicked(self, widget):
        self.stop = True
        self.emit('i-want-stop')

    def close(self, *args):
        self.destroy()

    def increase(self, anobject, command, *args):
        self.label.set_text(_('Executing: %s') % command)
        self.value += 1.0
        fraction = self.value/self.max_value
        self.progressbar.set_fraction(fraction)
        if self.value == self.max_value:
            self.hide()


def get_output_filename(file_in):
    head, tail = os.path.split(file_in)
    root, ext = os.path.splitext(tail)
    file_out = os.path.join(head, root+'.ogg')
    return file_out


def convert2ogg(file_in):
    tmp_file_out = tempfile.NamedTemporaryFile(
        prefix='tmp_convert2ogg_file_', dir='/tmp/').name
    tmp_file_out += '.ogg'
    rutine = 'ffmpeg -i "%s" \
    -acodec libvorbis \
    -ac 2 \
    -b:a 64k \
    -ar 22000 \
    "%s"' % (file_in, tmp_file_out)
    args = shlex.split(rutine)
    p = subprocess.Popen(args, stdout=subprocess.PIPE)
    out, err = p.communicate()
    file_out = get_output_filename(file_in)
    if os.path.exists(file_out):
        os.remove(file_out)
    shutil.copyfile(tmp_file_out, file_out)
    if os.path.exists(tmp_file_out):
        os.remove(tmp_file_out)


def get_files(files_in):
    files = []
    for file_in in files_in:
        print(file_in)
        file_in = unquote_plus(file_in.get_uri()[7:])
        if os.path.isfile(file_in):
            files.append(file_in)
    return files


class OGGConvereterMenuProvider(GObject.GObject, FileManager.MenuProvider):
    """
    Implements the 'Replace in Filenames' extension to the File Manager\
    right-click menu
    """

    def __init__(self):
        """
        File Manager crashes if a plugin doesn't implement the __init__\
        method
        """
        pass

    def all_files_are_sounds(self, items):
        for item in items:
            fileName, fileExtension = os.path.splitext(
                unquote_plus(item.get_uri()[7:]))
            if fileExtension.lower() in EXTENSIONS_FROM:
                return True
        return False

    def convert(self, menu, selected):
        files = get_files(selected)
        diib = DoItInBackground(convert2ogg, files)
        progreso = Progreso(_('Convert to ogg'), None, len(files))
        diib.connect('done_one', progreso.increase)
        diib.connect('ended', progreso.close)
        progreso.connect('i-want-stop', diib.stopit)
        diib.start()

    def get_file_items(self, window, sel_items):
        """
        Adds the 'Replace in Filenames' menu item to the File Manager\
        right-click menu, connects its 'activate' signal to the 'run'\
        method passing the selected Directory/File
        """
        if self.all_files_are_sounds(sel_items):
            top_menuitem = FileManager.MenuItem(
                name='OGGConverterMenuProvider::Gtk-ogg-tools',
                label=_('Convert to ogg'),
                tip=_('Tool to convert to ogg'))
            top_menuitem.connect('activate', self.convert, sel_items)
            #
            return top_menuitem,
        return
if __name__ == '__main__':
    print(tempfile.NamedTemporaryFile(
        prefix='tmp_convert2ogg_file', dir='/tmp/').name)
    print(get_output_filename('ejemplo.ext'))
