# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, James Beal <james_@catbus.co.uk>, ' \
                '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Crop a pdf file
'''

import sys
import re
from decimal import Decimal
from optparse import OptionGroup, Option

from calibre.ebooks.metadata.meta import metadata_from_formats
from calibre.ebooks.metadata import authors_to_string
from calibre.utils.config import OptionParser
from calibre.utils.logging import Log
from calibre.constants import preferred_encoding
from calibre.customize.conversion import OptionRecommendation
from calibre.ebooks.pdf.verify import is_valid_pdf, is_encrypted

from pyPdf import PdfFileWriter, PdfFileReader

DEFAULT_CROP = 10

USAGE = '\n%prog %%name ' + _('''\
[options] file.pdf

Crop a PDF file.
''')

OPTIONS = set([
    OptionRecommendation(name='output', recommended_value='cropped.pdf',
        level=OptionRecommendation.HIGH, long_switch='output', short_switch='o',
        help=_('Path to output file. By default a file is created in the current directory.')),
    OptionRecommendation(name='bottom_left_x', recommended_value=DEFAULT_CROP,
        level=OptionRecommendation.LOW, long_switch='left-x', short_switch='x',
        help=_('Number of pixels to crop from the left most x (default is %s)') % DEFAULT_CROP),
    OptionRecommendation(name='bottom_left_y', recommended_value=DEFAULT_CROP,
        level=OptionRecommendation.LOW, long_switch='left-y', short_switch='y',
        help=_('Number of pixels to crop from the left most y (default is %s)') % DEFAULT_CROP),
    OptionRecommendation(name='top_right_x', recommended_value=DEFAULT_CROP,
        level=OptionRecommendation.LOW, long_switch='right-x', short_switch='v',
        help=_('Number of pixels to crop from the right most x (default is %s)') % DEFAULT_CROP),
    OptionRecommendation(name='top_right_y', recommended_value=DEFAULT_CROP,
        level=OptionRecommendation.LOW, long_switch='right-y', short_switch='w',
        help=_('Number of pixels to crop from the right most y (default is %s)') % DEFAULT_CROP),
    OptionRecommendation(name='bounding', recommended_value=None,
        level=OptionRecommendation.LOW, long_switch='bounding', short_switch='b',
        help=_('A file generated by ghostscript which allows each page to be individually cropped `gs -dSAFER -dNOPAUSE -dBATCH -sDEVICE=bbox file.pdf 2> bounding`')),
])

def print_help(parser, log):
    help = parser.format_help().encode(preferred_encoding, 'replace')
    log(help)

def option_parser(name):
    usage = USAGE.replace('%%name', name)
    return OptionParser(usage=usage)

def option_recommendation_to_cli_option(add_option, rec):
    opt = rec.option
    switches = ['-'+opt.short_switch] if opt.short_switch else []
    switches.append('--'+opt.long_switch)
    attrs = dict(dest=opt.name, help=opt.help,
                     choices=opt.choices, default=rec.recommended_value)
    add_option(Option(*switches, **attrs))

def add_options(parser):
    group = OptionGroup(parser, _('Crop Options:'), _('Options to control the transformation of pdf'))
    parser.add_option_group(group)
    add_option = group.add_option

    for rec in OPTIONS:
        option_recommendation_to_cli_option(add_option, rec)

def crop_pdf(pdf_path, opts, metadata=None):
    if metadata == None:
        title = _('Unknown')
        author = _('Unknown')
    else:
        title = metadata.title
        author = authors_to_string(metadata.authors)

    input_pdf = PdfFileReader(open(pdf_path, 'rb'))

    bounding_lines = []
    if opts.bounding != None:
        try:
            bounding = open(opts.bounding , 'r')
            bounding_regex = re.compile('%%BoundingBox: (?P<bottom_x>\d+) (?P<bottom_y>\d+) (?P<top_x>\d+) (?P<top_y>\d+)')
        except:
            raise Exception('Error reading %s' % opts.bounding)

        lines = bounding.readlines()
        for line in lines:
            if line.startswith('%%BoundingBox:'):
                bounding_lines.append(line)
        if len(bounding_lines) != input_pdf.numPages:
            raise Exception('Error bounding file %s page count does not correspond to specified pdf' % opts.bounding)

    output_pdf = PdfFileWriter(title=title,author=author)
    blines = iter(bounding_lines)
    for page in input_pdf.pages:
        if bounding_lines != []:
            mo = bounding_regex.search(blines.next())
            if mo == None:
                raise Exception('Error in bounding file %s' % opts.bounding)
            page.mediaBox.upperRight = (float(mo.group('top_x')), Decimal(mo.group('top_y')))
            page.mediaBox.lowerLeft  = (float(mo.group('bottom_x')), Decimal(mo.group('bottom_y')))
        else:
            page.mediaBox.upperRight = (page.bleedBox.getUpperRight_x() - Decimal(opts.top_right_x), page.bleedBox.getUpperRight_y() - Decimal(opts.top_right_y))
            page.mediaBox.lowerLeft  = (page.bleedBox.getLowerLeft_x() + Decimal(opts.bottom_left_x), page.bleedBox.getLowerLeft_y() + Decimal(opts.bottom_left_y))
        output_pdf.addPage(page)

    with open(opts.output, 'wb') as output_file:
        output_pdf.write(output_file)

def main(args=sys.argv, name=''):
    log = Log()
    parser = option_parser(name)
    add_options(parser)

    opts, args = parser.parse_args(args)
    args = args[1:]

    if len(args) < 1:
        print 'Error: A PDF file is required.\n'
        print_help(parser, log)
        return 1

    if not is_valid_pdf(args[0]):
        print 'Error: Could not read file `%s`.' % args[0]
        return 1

    if is_encrypted(args[0]):
        print 'Error: file `%s` is encrypted.' % args[0]
        return 1

    mi = metadata_from_formats([args[0]])

    crop_pdf(args[0], opts, mi)

    return 0

if __name__ == '__main__':
    sys.exit(main())
