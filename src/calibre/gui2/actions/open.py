#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.gui2.actions import InterfaceAction

class OpenFolderAction(InterfaceAction):

    name = 'Open Folder'
    action_spec = (_('Open containing folder'), 'document_open.svg', None,
            _('O'))

    def genesis(self):
        self.action_open_containing_folder.triggered.connect(self.iactions['View'].view_folder)

    def location_selected(self, loc):
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)


