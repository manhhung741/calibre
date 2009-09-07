#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.web.feeds.news import BasicNewsRecipe

class ATV(BasicNewsRecipe):
     title          = u'ATV'
     oldest_article = 5
     max_articles_per_feed = 50
     language = 'hu'

     __author__ = 'Ezmegaz'


     feeds          = [(u'H\xedrek', u'http://atv.hu/rss/1'), (u'Cikkek',
 u'http://atv.hu/rss/2')]

