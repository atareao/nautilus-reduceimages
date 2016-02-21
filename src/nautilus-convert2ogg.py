#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# This file is part of nautilus-pdf-tools
#
# Copyright (C) 2012-2015 Lorenzo Carbonell
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
import os
import subprocess
import shlex
import threading
import tempfile
import shutil
from Queue import Queue
from urllib import unquote_plus
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import GLib
from gi.repository import Nautilus as FileManager

EXTENSIONS_FROM = ['.mp3','.wav','.ogg']
SEPARATOR = u'\u2015' * 10
NUM_THREADS = 4

_ = str

def get_output_filename(file_in):
	head, tail = os.path.split(file_in)
	root, ext = os.path.splitext(tail)
	file_out = os.path.join(head,root+'.ogg')
	return file_out

def convert2ogg(file_in):
	tmp_file_out = tempfile.NamedTemporaryFile(prefix='tmp_convert2ogg_file_', dir='/tmp/').name
	tmp_file_out += '.ogg'
	rutine = 'ffmpeg -i "%s" \
	-acodec libvorbis \
	-ac 2 \
	-b:a 64k \
	-ar 22000 \
	"%s"'%(file_in,tmp_file_out)
	args = shlex.split(rutine)
	p = subprocess.Popen(args,stdout = subprocess.PIPE)
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


class Manager(GObject.GObject):
	def __init__(self,files):
		self.files = files
	
	def process(self):
		total = len(self.files)
		if total>0:
			print(self.files)
			workers = []
			print('1.- Starting process creating workers')
			cua = Queue(maxsize=total+1)
			progreso = Progreso('Converting files...',None,total)
			total_workers = total if NUM_THREADS > total else NUM_THREADS
			for i in range(total_workers):
				worker = Worker(cua)
				worker.connect('converted',GLib.idle_add, progreso.increase)
				worker.start()
				workers.append(worker)
			print('2.- Puting task in the queue')
			for afile in self.files:
				cua.put(afile)
			print('3.- Block until all tasks are done')
			cua.join()
			print('4.- Stopping workers')
			for i in range(total_workers):
				cua.put(None)
			for worker in workers:
				worker.join()
				while Gtk.events_pending():
					Gtk.main_iteration()				
			print('5.- The End')


class Worker(GObject.GObject,threading.Thread):
	__gsignals__ = {
		'converted':(GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE,(object,)),
		}
	
	def __init__(self,cua):
		threading.Thread.__init__(self)
		GObject.GObject.__init__(self)		
		self.setDaemon(True)
		self.cua = cua

	def run(self):
		while True:
			file_in = self.cua.get()
			if file_in is None:
				break
			try:
				convert2ogg(file_in)				
			except Exception as e:
				print(e)
			self.emit('converted',file_in)
			self.cua.task_done()

class Progreso(Gtk.Dialog):
	def __init__(self,title,parent,max_value):
		#
		Gtk.Dialog.__init__(self,title,parent)
		self.set_position(Gtk.WindowPosition.CENTER_ALWAYS)
		self.set_size_request(330, 40)
		self.set_resizable(False)
		self.connect('destroy', self.close)
		#
		vbox1 = Gtk.VBox(spacing = 5)
		vbox1.set_border_width(5)
		self.get_content_area().add(vbox1)
		#
		self.progressbar = Gtk.ProgressBar()
		vbox1.pack_start(self.progressbar,True,True,0)
		#
		self.show_all()
		#
		self.max_value=max_value
		self.value=0.0

	def close(self,widget=None):
		self.destroy()

	def increase(self):
		self.value+=1.0
		fraction=self.value/self.max_value
		self.progressbar.set_fraction(fraction)
		if self.value==self.max_value:
			self.hide()
		return False

"""
Tools to manipulate sounds
"""	
class OGGConvereterMenuProvider(GObject.GObject, FileManager.MenuProvider):
	"""Implements the 'Replace in Filenames' extension to the File Manager right-click menu"""

	def __init__(self):
		"""File Manager crashes if a plugin doesn't implement the __init__ method"""
		pass

	def all_files_are_sounds(self,items):
		for item in items:
			fileName, fileExtension = os.path.splitext(unquote_plus(item.get_uri()[7:]))
			if fileExtension.lower() in EXTENSIONS_FROM:
				return True
		return False
				
	def convert(self,menu,selected):
		files = get_files(selected)
		manager = Manager(files)
		manager.process()

	def get_file_items(self, window, sel_items):
		"""Adds the 'Replace in Filenames' menu item to the File Manager right-click menu,
		   connects its 'activate' signal to the 'run' method passing the selected Directory/File"""
		if self.all_files_are_sounds(sel_items):
			top_menuitem = FileManager.MenuItem(name='OGGConverterMenuProvider::Gtk-ogg-tools',
									 label=_('Convert to ogg'),
									 tip=_('Tool to convert to ogg'))
			top_menuitem.connect('activate', self.convert, sel_items)
			#		
			return top_menuitem,
		return
if __name__ == '__main__':
	print(tempfile.NamedTemporaryFile(prefix='tmp_convert2ogg_file', dir='/tmp/').name)
	print(get_output_filename('ejemplo.ext'))
