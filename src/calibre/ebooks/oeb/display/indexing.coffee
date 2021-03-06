#!/usr/bin/env coffee
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

###
 Copyright 2012, Kovid Goyal <kovid@kovidgoyal.net>
 Released under the GPLv3 License
###

window_scroll_pos = (win=window) -> # {{{
    if typeof(win.pageXOffset) == 'number'
        x = win.pageXOffset
        y = win.pageYOffset
    else # IE < 9
        if document.body and ( document.body.scrollLeft or document.body.scrollTop )
            x = document.body.scrollLeft
            y = document.body.scrollTop
        else if document.documentElement and ( document.documentElement.scrollLeft or document.documentElement.scrollTop)
            y = document.documentElement.scrollTop
            x = document.documentElement.scrollLeft
    return [x, y]
# }}}

viewport_to_document = (x, y, doc=window?.document) -> # {{{
    until doc == window.document
        # We are in a frame
        frame = doc.defaultView.frameElement
        rect = frame.getBoundingClientRect()
        x += rect.left
        y += rect.top
        doc = frame.ownerDocument
    win = doc.defaultView
    [wx, wy] = window_scroll_pos(win)
    x += wx
    y += wy
    return [x, y]
# }}}

class BookIndexing
    ###
    This class is a namespace to expose indexing functions via the
    window.book_indexing object. The most important functions are:

    anchor_positions(): Get the absolute (document co-ordinate system) position
    for elements with the specified id/name attributes.

    ###

    constructor: () ->
        this.cache = {}
        this.last_check = [null, null]

    cache_valid: (anchors) ->
        for a in anchors
            if not Object.prototype.hasOwnProperty.call(this.cache, a)
                return false
        for p of this.cache
            if Object.prototype.hasOwnProperty.call(this.cache, p) and p not in anchors
                return false
        return true

    anchor_positions: (anchors, use_cache=false) ->
        body = document.body
        doc_constant = body.scrollHeight == this.last_check[1] and body.scrollWidth == this.last_check[0]
        if use_cache and doc_constant and this.cache_valid(anchors)
            return this.cache

        ans = {}
        for anchor in anchors
            elem = document.getElementById(anchor)
            if elem == null
                # Look for an <a name="anchor"> element
                try
                    result = document.evaluate(
                        ".//*[local-name() = 'a' and @name='#{ anchor }']",
                        body, null,
                        XPathResult.FIRST_ORDERED_NODE_TYPE, null)
                    elem = result.singleNodeValue
                catch error
                    # The anchor had a ' or other invalid char
                    elem = null
            if elem == null
                pos = [body.scrollWidth+1000, body.scrollHeight+1000]
            else
                br = elem.getBoundingClientRect()
                pos = viewport_to_document(br.left, br.top, elem.ownerDocument)

            if window.paged_display?.in_paged_mode
                pos[0] = window.paged_display.column_at(pos[0])
            ans[anchor] = pos

        this.cache = ans
        this.last_check = [body.scrollWidth, body.scrollHeight]
        return ans

if window?
    window.book_indexing = new BookIndexing()

