#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008-2009, AprilHare, Darko Miletic <darko.miletic at gmail.com>'
'''
newscientist.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class NewScientist(BasicNewsRecipe):
    title                 = 'New Scientist - Online News'
    __author__            = 'Darko Miletic'
    description           = 'Science news and science articles from New Scientist.'
    language              = _('English')
    publisher             = 'New Scientist'
    category              = 'science news, science articles, science jobs, drugs, cancer, depression, computer software, sex'    
    delay                 = 3    
    oldest_article        = 7
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    remove_javascript     = True
    encoding              = 'utf-8'
    
    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"' 
    
    keep_only_tags = [dict(name='div', attrs={'id':['pgtop','maincol']})]

    remove_tags = [
                     dict(name='div', attrs={'class':['hldBd','adline','pnl','infotext' ]})
                    ,dict(name='div', attrs={'id'   :['compnl','artIssueInfo','artTools']})
                    ,dict(name='p'  , attrs={'class':['marker','infotext'               ]})
                  ]

    feeds          = [
                        (u'Latest Headlines'        , u'http://feeds.newscientist.com/science-news'              )
                       ,(u'Magazine'                , u'http://www.newscientist.com/feed/magazine'               )                      
                       ,(u'Health'                  , u'http://www.newscientist.com/feed/view?id=2&type=channel' )
                       ,(u'Life'                    , u'http://www.newscientist.com/feed/view?id=3&type=channel' )
                       ,(u'Space'                   , u'http://www.newscientist.com/feed/view?id=6&type=channel' )
                       ,(u'Physics and Mathematics' , u'http://www.newscientist.com/feed/view?id=4&type=channel' )
                       ,(u'Environment'             , u'http://www.newscientist.com/feed/view?id=1&type=channel' )
                       ,(u'Science in Society'      , u'http://www.newscientist.com/feed/view?id=5&type=channel' )
                       ,(u'Tech'                    , u'http://www.newscientist.com/feed/view?id=7&type=channel' )
                     ]

    def get_article_url(self, article):
        url = article.get('link',  None)
        raw = article.get('description',  None)
        rsoup = self.index_to_soup(raw)
        atags = rsoup.findAll('a',href=True)
        for atag in atags:
            if atag['href'].startswith('http://res.feedsportal.com/viral/sendemail2.html?'):
               st, sep, rest = atag['href'].partition('&link=')
               real_url, sep2, drest = rest.partition('" target=')
               return real_url
        return url

    def print_version(self, url):
        rawurl, sep, params = url.partition('?')
        return rawurl + '?full=true&print=true'
                     