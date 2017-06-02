#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of nautilus-lo-compress
#
# Copyright (C) 2017 Lorenzo Carbonell
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
    gi.require_version('GObject', '2.0')
    gi.require_version('GLib', '2.0')
    gi.require_version('Nautilus', '3.0')
except Exception as e:
    print(e)
    exit(-1)
from gi.repository import Gtk
from gi.repository import GObject
from gi.repository import GLib
from gi.repository import Nautilus as FileManager
from zipfile import ZipFile
import zipfile
import tempfile
import os
import shutil
from xml.etree import ElementTree
from PIL import Image
import ConfigParser
from threading import Thread
import mimetypes
from urllib import unquote_plus

APP = '$APP$'
VERSION = '$VERSION$'

CONFIG_DIR = os.path.join(os.path.expanduser('~'), '.config', APP.lower())
if not os.path.exists(CONFIG_DIR):
    os.makedirs(CONFIG_DIR)
CONFIG_FILE = os.path.join(CONFIG_DIR, '{0}.conf'.format(APP.lower()))

MARGIN = 10

_ = str


def get_files(files_in):
    files = []
    for file_in in files_in:
        print(file_in)
        file_in = unquote_plus(file_in.get_uri()[7:])
        if os.path.isfile(file_in):
            files.append(file_in)
    return files


def zipdir(path, ziph):
    # ziph is zipfile handle
    for root, dirs, files in os.walk(path):
        for file in files:
            arcname = os.path.join(os.path.relpath(root, path), file)
            ziph.write(os.path.join(root, file), arcname)


def to_mm(value):
    if value.endswith('cm'):
        return float(value[:-2]) * 10.0
    elif value.endswith('mm'):
        return float(value[:-2])
    elif value.endswith('in'):
        return float(value[:-2]) * 25.4


def reduce_lo_file(orginalFile, dpi=300, quality=80, optimize=True):
    filename, fileextension = os.path.splitext(orginalFile)
    destFile = '{0}_reduced{1}'.format(filename, fileextension)

    temporalFile = tempfile.NamedTemporaryFile().name
    if os.path.exists(temporalFile):
        os.remove(temporalFile)

    temporalDir = tempfile.mkdtemp()
    if os.path.exists(temporalDir):
        shutil.rmtree(temporalDir, True)
    os.makedirs(temporalDir)

    with ZipFile(orginalFile, 'r') as myzip:
        for element in myzip.infolist():
            myzip.extract(element, temporalDir)

    ns = {'draw': 'urn:oasis:names:tc:opendocument:xmlns:drawing:1.0',
          'svg': 'urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0'}
    eTree = ElementTree.parse(os.path.join(temporalDir, 'content.xml'))
    root = eTree.getroot()
    for node in root.findall('.//draw:frame', ns):
        width = to_mm(node.attrib['{%s}%s' % (ns['svg'], 'width')])
        height = to_mm(node.attrib['{%s}%s' % (ns['svg'], 'height')])
        aimage = node.find('draw:image', ns).attrib[
            '{http://www.w3.org/1999/xlink}href']
        afile = os.path.join(temporalDir, aimage)
        size = (width / 25.4 * dpi, height / 25.4 * dpi)
        im = Image.open(afile)
        im.thumbnail(size, Image.ANTIALIAS)
        im.save(afile, quality=quality, optimize=optimize)

    with ZipFile(temporalFile, 'w', zipfile.ZIP_DEFLATED) as output:
            zipdir(temporalDir, output)

    if os.path.exists(destFile):
        os.remove(destFile)

    shutil.move(temporalFile, destFile)

    if os.path.exists(temporalDir):
        shutil.rmtree(temporalDir, True)


def read_config():
    config = ConfigParser.ConfigParser()
    config.read(CONFIG_FILE)
    try:
        dpi = config.getint('Config', 'dpi')
        quality = config.getint('Config', 'quality')
        optimize = config.getboolean('Config', 'optimize')
        return dpi, quality, optimize
    except ConfigParser.NoSectionError as e:
        print(e)
        write_config(300, 80, True)
    return 300, 80, True


def write_config(dpi=300, quality=80, optimize=True):
    config = ConfigParser.ConfigParser()
    with open(CONFIG_FILE, 'w') as configfile:
        config.add_section('Config')
        config.set('Config', 'dpi', dpi)
        config.set('Config', 'quality', quality)
        config.set('Config', 'optimize', optimize)
        config.write(configfile)


class ProgressDialog(Gtk.Dialog):
    __gsignals__ = {
        'i-want-stop': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, ()),
    }

    def __init__(self, title, parent, max_value):
        Gtk.Dialog.__init__(self, title, parent)
        self.set_position(Gtk.WindowPosition.CENTER_ALWAYS)
        self.set_size_request(330, 30)
        self.set_resizable(False)
        self.connect('destroy', self.close)
        self.set_modal(True)
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

    def emit(self, *args):
        GLib.idle_add(GObject.GObject.emit, self, *args)

    def set_max_value(self, anobject, max_value):
        self.max_value = float(max_value)

    def get_stop(self):
        return self.stop

    def on_button_stop_clicked(self, widget):
        self.stop = True
        self.emit('i-want-stop')

    def close(self, *args):
        self.destroy()

    def set_element(self, anobject, element):
        self.label.set_text(_('Compress: %s') % element)

    def increase(self, anobject, value):
        self.value += float(value)
        fraction = self.value / self.max_value
        self.progressbar.set_fraction(fraction)
        if self.value == self.max_value:
            self.hide()


class DoItInBackground(GObject.GObject, Thread):
    __gsignals__ = {
        'started': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, (int,)),
        'ended': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, (bool,)),
        'start_one': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, (str,)),
        'end_one': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, (int,)),
    }

    def __init__(self, elements):
        GObject.GObject.__init__(self)
        Thread.__init__(self)
        self.elements = elements
        self.stopit = False
        self.ok = True
        self.daemon = True
        self.process = None

    def emit(self, *args):
        GLib.idle_add(GObject.GObject.emit, self, *args)

    def stop(self, *args):
        self.stopit = True

    def compress_file(self, file_in, dpi, quality, optimize):
        reduce_lo_file(file_in, dpi, quality, optimize)

    def run(self):
        dpi, quality, optimize = read_config()
        total = 0
        for element in self.elements:
            total += os.path.getsize(element)
        self.emit('started', total)
        try:
            for element in self.elements:
                print(element)
                if self.stopit is True:
                    self.ok = False
                    break
                self.emit('start_one', element)
                self.compress_file(element, dpi, quality, optimize)
                self.emit('end_one', os.path.getsize(element))
        except Exception as e:
            self.ok = False
        try:
            if self.process is not None:
                self.process.terminate()
                self.process = None
        except Exception as e:
            print(e)
        self.emit('ended', self.ok)


class ConfigDialog(Gtk.Dialog):

    def __init__(self, title, parent):
        Gtk.Dialog.__init__(self,
                            title,
                            parent,
                            Gtk.DialogFlags.MODAL |
                            Gtk.DialogFlags.DESTROY_WITH_PARENT,
                            (Gtk.STOCK_CANCEL, Gtk.ResponseType.REJECT,
                             Gtk.STOCK_OK, Gtk.ResponseType.ACCEPT))

        self.set_position(Gtk.WindowPosition.CENTER_ALWAYS)
        self.set_resizable(False)
        self.connect('destroy', self.close)
        self.set_modal(True)

        frame = Gtk.Frame()
        frame.set_margin_top(MARGIN)
        frame.set_margin_bottom(MARGIN)
        frame.set_margin_right(MARGIN)
        frame.set_margin_left(MARGIN)
        self.get_content_area().add(frame)

        grid = Gtk.Grid()
        grid.set_margin_top(MARGIN)
        grid.set_margin_bottom(MARGIN)
        grid.set_margin_right(MARGIN)
        grid.set_margin_left(MARGIN)
        grid.set_row_spacing(MARGIN)
        grid.set_row_homogeneous(False)
        grid.set_column_spacing(MARGIN)
        grid.set_column_homogeneous(False)
        frame.add(grid)
        #
        label = Gtk.Label('dpi' + ':')
        label.set_alignment(0.0, 0.5)
        grid.attach(label, 0, 0, 1, 1)
        self.dpi = Gtk.HScale.new_with_range(0, 600, 50)
        self.dpi.set_size_request(200, 0)
        grid.attach(self.dpi, 1, 0, 1, 1)
        label = Gtk.Label('quality' + ':')
        label.set_alignment(0.0, 0.5)
        grid.attach(label, 0, 1, 1, 1)
        self.quality = Gtk.HScale.new_with_range(0, 100, 1)
        grid.attach(self.quality, 1, 1, 1, 1)
        label = Gtk.Label('Optimize' + ':')
        label.set_alignment(0.0, 0.5)
        grid.attach(label, 0, 2, 1, 1)
        box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 5)
        grid.attach(box, 1, 2, 1, 1)
        self.optimize = Gtk.Switch()
        box.pack_start(self.optimize, False, False, 0)

        dpi, quality, optimize = read_config()
        self.dpi.set_value(dpi)
        self.quality.set_value(quality)
        self.optimize.set_active(optimize)

        self.show_all()

    def save(self):
        dpi = int(self.dpi.get_value())
        quality = int(self.quality.get_value())
        optimize = self.optimize.get_active()
        write_config(dpi=dpi, quality=quality, optimize=optimize)


class CompressODTFileMenuProvider(GObject.GObject, FileManager.MenuProvider):
    """
    Implements the 'Replace in Filenames' extension to the File Manager\
    right-click menu
    """

    def __init__(self):
        """
        File Manager crashes if a plugin doesn't implement the __init__\
        method
        """
        mimetypes.init()
        pass

    def all_are_odt_files(self, items):
        for item in items:
            file_in = unquote_plus(item.get_uri()[7:])
            if not os.path.isfile(file_in):
                return False
            mimetype = mimetypes.guess_type('file://' + file_in)[0]
            if mimetype != 'application/vnd.oasis.opendocument.text':
                return False
        return True

    def compressodt(self, menu, selected, window):
        odtfiles = get_files(selected)
        diib = DoItInBackground(odtfiles)
        progreso = ProgressDialog(_('Compress ODT file'),
                                  window,
                                  len(odtfiles))
        diib.connect('started', progreso.set_max_value)
        diib.connect('start_one', progreso.set_element)
        diib.connect('end_one', progreso.increase)
        diib.connect('ended', progreso.close)
        progreso.connect('i-want-stop', diib.stop)
        diib.start()
        progreso.run()

    def get_file_items(self, window, sel_items):
        """
        Adds the 'Replace in Filenames' menu item to the File Manager\
        right-click menu, connects its 'activate' signal to the 'run'\
        method passing the selected Directory/File
        """
        top_menuitem = FileManager.MenuItem(
            name='CompressODTFileMenuProvider::Gtk-compressodt-top',
            label=_('Compress ODT files') + '...',
            tip=_('Tool to compress ODT files'))
        submenu = FileManager.Menu()
        top_menuitem.set_submenu(submenu)

        sub_menuitem_00 = FileManager.MenuItem(
            name='CompressODTFileMenuProvider::Gtk-compressodt-sub-00',
            label=_('Compress ODT files'),
            tip=_('Tool to compress ODT files'))
        if self.all_are_odt_files(sel_items):
            sub_menuitem_00.connect('activate',
                                    self.compressodt,
                                    sel_items,
                                    window)
        else:
            sub_menuitem_00.set_property('sensitive', False)
        submenu.append_item(sub_menuitem_00)

        sub_menuitem_01 = FileManager.MenuItem(
            name='CompressODTFileMenuProvider::Gtk-compressodt-sub-01',
            label=_('Configurate'),
            tip=_('Configurate tool to compress ODT files'))
        sub_menuitem_01.connect('activate', self.config, window)
        submenu.append_item(sub_menuitem_01)

        sub_menuitem_02 = FileManager.MenuItem(
            name='CompressODTFileMenuProvider::Gtk-compressodt-sub-02',
            label=_('About'),
            tip=_('About'))
        sub_menuitem_02.connect('activate', self.about, window)
        submenu.append_item(sub_menuitem_02)

        return top_menuitem,

    def config(self, widget, window):
        configDialog = ConfigDialog('Config LO Compress', window)
        if configDialog.run() == Gtk.ResponseType.ACCEPT:
            configDialog.hide()
            configDialog.save()
        configDialog.destroy()

    def about(self, widget, window):
        ad = Gtk.AboutDialog(parent=window)
        ad.set_name(APP)
        ad.set_version(VERSION)
        ad.set_copyright('Copyrignt (c) 2017\nLorenzo Carbonell')
        ad.set_comments(APP)
        ad.set_license('''
This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program. If not, see <http://www.gnu.org/licenses/>.
''')
        ad.set_website('http://www.atareao.es')
        ad.set_website_label('http://www.atareao.es')
        ad.set_authors([
            'Lorenzo Carbonell <lorenzo.carbonell.cerezo@gmail.com>'])
        ad.set_documenters([
            'Lorenzo Carbonell <lorenzo.carbonell.cerezo@gmail.com>'])
        ad.set_icon_name(APP)
        ad.set_logo_icon_name(APP)
        ad.run()
        ad.destroy()


if __name__ == '__main__':
    files = ['/home/lorenzo/Escritorio/test1.odt',
             '/home/lorenzo/Escritorio/test2.odt',
             '/home/lorenzo/Escritorio/test3.odt',
             '/home/lorenzo/Escritorio/test4.odt',
             '/home/lorenzo/Escritorio/test5.odt']
    # reduce_lo_file(orginalFile)
    configDialog = ConfigDialog('test', None)
    if configDialog.run() == Gtk.ResponseType.ACCEPT:
        configDialog.hide()
        configDialog.save()
    configDialog.destroy()
    pd = ProgressDialog('Test', None, len(files))
    diib = DoItInBackground(files)
    diib.connect('started', pd.set_max_value)
    diib.connect('start_one', pd.set_element)
    diib.connect('end_one', pd.increase)
    diib.connect('ended', pd.close)
    pd.connect('i-want-stop', diib.stop)
    diib.run()
    #pd = ProgressDialog('Test', None, 5)
    pd.run()
