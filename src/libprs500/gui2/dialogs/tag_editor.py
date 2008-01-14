##    Copyright (C) 2008 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
from PyQt4.QtCore import SIGNAL, Qt
from PyQt4.QtGui import QDialog

from libprs500.gui2.dialogs.tag_editor_ui import Ui_TagEditor
from libprs500.gui2 import qstring_to_unicode

class TagEditor(QDialog, Ui_TagEditor):
    
    def __init__(self, window, db, index):
        QDialog.__init__(self, window)
        Ui_TagEditor.__init__(self)
        self.setupUi(self)
        
        self.db = db
        self.index = index
        tags = self.db.tags(self.index)
        if tags:
            tags = [tag.lower().strip() for tag in tags.split(',') if tag.strip()]
            tags.sort()
            for tag in tags:
                self.applied_tags.addItem(tag)
        else:
            tags = []
        
        self.tags = tags
        
        all_tags = [tag.lower() for tag in self.db.all_tags()]
        all_tags = list(set(all_tags))
        all_tags.sort()
        for tag in all_tags:
            if tag not in tags:
                self.available_tags.addItem(tag)
                
        self.connect(self.apply_button, SIGNAL('clicked()'), self.apply_tags)
        self.connect(self.unapply_button, SIGNAL('clicked()'), self.unapply_tags)
        self.connect(self.add_tag_button, SIGNAL('clicked()'), self.add_tag)
        self.connect(self.add_tag_input, SIGNAL('returnPressed()'), self.add_tag)
        self.connect(self.available_tags, SIGNAL('itemActivated(QListWidgetItem*)'), self.apply_tags)
        self.connect(self.applied_tags, SIGNAL('itemActivated(QListWidgetItem*)'), self.unapply_tags)
    
    def apply_tags(self, item=None):
        items = self.available_tags.selectedItems() if item is None else [item]  
        for item in items:
            tag = qstring_to_unicode(item.text())
            self.tags.append(tag)
            self.available_tags.takeItem(self.available_tags.row(item))
        
        self.tags.sort()
        self.applied_tags.clear()
        for tag in self.tags:
            self.applied_tags.addItem(tag)
                
            
    
    def unapply_tags(self, item=None):
        items = self.available_tags.selectedItems() if item is None else [item] 
        for item in items:
            tag = qstring_to_unicode(item.text())
            self.tags.remove(tag)
            self.available_tags.addItem(tag)
            
        self.tags.sort()
        self.applied_tags.clear()
        for tag in self.tags:
            self.applied_tags.addItem(tag)
            
        self.available_tags.sortItems()
    
    def add_tag(self):
        tags = qstring_to_unicode(self.add_tag_input.text()).lower().split(',')
        for tag in tags:
            tag = tag.strip()
            for item in self.available_tags.findItems(tag, Qt.MatchFixedString):
                self.available_tags.takeItem(self.available_tags.row(item))
            if tag not in self.tags:
                self.tags.append(tag)
                
        self.tags.sort()
        self.applied_tags.clear()
        for tag in self.tags:
            self.applied_tags.addItem(tag)
            
        self.add_tag_input.setText('')
