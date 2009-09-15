from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import os, glob, re, textwrap

from lxml import etree

from calibre.customize.conversion import InputFormatPlugin

class InlineClass(etree.XSLTExtension):

    FMTS = ('italics', 'bold', 'underlined', 'strike-through', 'small-caps')

    def __init__(self, log):
        etree.XSLTExtension.__init__(self)
        self.log = log
        self.font_sizes = []
        self.colors = []

    def execute(self, context, self_node, input_node, output_parent):
        classes = []
        for x in self.FMTS:
            cls = x if input_node.get(x, None) == 'true' else 'no-'+x
            classes.append(cls)
        none = True
        for x in self.FMTS:
            if 'no-'+x not in classes:
                none = False
                break
        if none:
            classes = ['none']
        fs = input_node.get('font-size', False)
        if fs:
            if fs not in self.font_sizes:
                self.font_sizes.append(fs)
            classes.append('fs%d'%self.font_sizes.index(fs))
        fc = input_node.get('font-color', False)
        if fc:
            if fc not in self.colors:
                self.colors.append(fc)
            classes.append('col%d'%self.colors.index(fc))

        output_parent.text = ' '.join(classes)


class RTFInput(InputFormatPlugin):

    name        = 'RTF Input'
    author      = 'Kovid Goyal'
    description = 'Convert RTF files to HTML'
    file_types  = set(['rtf'])

    def generate_xml(self, stream):
        from calibre.ebooks.rtf2xml.ParseRtf import ParseRtf
        ofile = 'out.xml'
        parser = ParseRtf(
            in_file    = stream,
            out_file   = ofile,
            # Convert symbol fonts to unicode equivalents. Default
            # is 1
            convert_symbol = 1,

            # Convert Zapf fonts to unicode equivalents. Default
            # is 1.
            convert_zapf = 1,

            # Convert Wingding fonts to unicode equivalents.
            # Default is 1.
            convert_wingdings = 1,

            # Convert RTF caps to real caps.
            # Default is 1.
            convert_caps = 1,

            # Indent resulting XML.
            # Default is 0 (no indent).
            indent = 1,

            # Form lists from RTF. Default is 1.
            form_lists = 1,

            # Convert headings to sections. Default is 0.
            headings_to_sections = 1,

            # Group paragraphs with the same style name. Default is 1.
            group_styles = 1,

            # Group borders. Default is 1.
            group_borders = 1,

            # Write or do not write paragraphs. Default is 0.
            empty_paragraphs = 0,
        )
        parser.parse_rtf()
        ans = open('out.xml').read()
        os.remove('out.xml')
        return ans

    def extract_images(self, picts):
        self.log('Extracting images...')
        count = 0
        raw = open(picts, 'rb').read()
        starts = []
        for match in re.finditer(r'\{\\pict([^}]+)\}', raw):
            starts.append(match.start(1))

        imap = {}

        for start in starts:
            pos, bc = start, 1
            while bc > 0:
                if raw[pos] == '}': bc -= 1
                elif raw[pos] == '{': bc += 1
                pos += 1
            pict = raw[start:pos+1]
            enc = re.sub(r'[^a-zA-Z0-9]', '', pict)
            if len(enc) % 2 == 1:
                enc = enc[:-1]
            data = enc.decode('hex')
            ext = '.jpg'
            if 'EMF' in data[:200]:
                ext = '.wmf'
            elif 'PNG' in data[:200]:
                ext = '.png'
            count += 1
            name = (('%4d'%count).replace(' ', '0'))+ext
            open(name, 'wb').write(data)
            imap[count] = name
            #open(name+'.hex', 'wb').write(enc)
        return imap

    def write_inline_css(self, ic):
        font_size_classes = ['span.fs%d { font-size: %spt }'%(i, x) for i, x in
                enumerate(ic.font_sizes)]
        color_classes = ['span.col%d { color: %s }'%(i, x) for i, x in
                enumerate(ic.colors)]
        css = textwrap.dedent('''
        span.none {
            text-decoration: none; font-weight: normal;
            font-style: normal; font-variant: normal
        }

        span.italics { font-style: italic }
        span.no-italics { font-style: normal }

        span.bold { font-weight: bold }
        span.no-bold { font-weight: normal }

        span.small-caps { font-variant: small-caps }
        span.no-small-caps { font-variant: normal }

        span.underlined { text-decoration: underline }
        span.no-underlined { text-decoration: none }

        span.strike-through { text-decoration: line-through }
        span.no-strike-through { text-decoration: none }

        ''')
        css += '\n'+'\n'.join(font_size_classes)
        css += '\n' +'\n'.join(color_classes)
        with open('styles.css', 'ab') as f:
            f.write(css)


    def convert(self, stream, options, file_ext, log,
                accelerators):
        from calibre.ebooks.metadata.meta import get_metadata
        from calibre.ebooks.metadata.opf2 import OPFCreator
        from calibre.ebooks.rtf2xml.ParseRtf import RtfInvalidCodeException
        self.log = log
        self.log('Converting RTF to XML...')
        try:
            xml = self.generate_xml(stream.name)
        except RtfInvalidCodeException:
            raise ValueError(_('This RTF file has a feature calibre does not '
            'support. Convert it to HTML first and then try it.'))
        d = glob.glob(os.path.join('*_rtf_pict_dir', 'picts.rtf'))
        if d:
            imap = {}
            try:
                imap = self.extract_images(d[0])
            except:
                self.log.exception('Failed to extract images...')
        self.log('Parsing XML...')
        parser = etree.XMLParser(recover=True, no_network=True)
        doc = etree.fromstring(xml, parser=parser)
        for pict in doc.xpath('//rtf:pict[@num]',
                namespaces={'rtf':'http://rtf2xml.sourceforge.net/'}):
            num = int(pict.get('num'))
            name = imap.get(num, None)
            if name is not None:
                pict.set('num', name)
        self.log('Converting XML to HTML...')
        inline_class = InlineClass(self.log)
        styledoc = etree.fromstring(P('templates/rtf.xsl', data=True))

        extensions = { ('calibre', 'inline-class') : inline_class }
        transform = etree.XSLT(styledoc, extensions=extensions)
        result = transform(doc)
        html = 'index.xhtml'
        with open(html, 'wb') as f:
            res = transform.tostring(result)
            res = res[:100].replace('xmlns:html', 'xmlns') + res[100:]
            f.write(res)
        self.write_inline_css(inline_class)
        stream.seek(0)
        mi = get_metadata(stream, 'rtf')
        if not mi.title:
            mi.title = _('Unknown')
        if not mi.authors:
            mi.authors = [_('Unknown')]
        opf = OPFCreator(os.getcwd(), mi)
        opf.create_manifest([('index.xhtml', None)])
        opf.create_spine(['index.xhtml'])
        opf.render(open('metadata.opf', 'wb'))
        return os.path.abspath('metadata.opf')

