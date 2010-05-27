'''
    Device driver for iTunes

    GRiker

    22 May 2010
'''
import cStringIO, datetime, os, re, shutil, sys, time

from calibre import fit_image
from calibre.constants import isosx, iswindows
from calibre.devices.interface import DevicePlugin
from calibre.ebooks.metadata import MetaInformation
from calibre.library.server.utils import strftime
from calibre.utils.config import Config
from calibre.utils.date import parse_date

from PIL import Image as PILImage


if isosx:
    print "running in OSX"
    import appscript, osax

if iswindows:
    print "running in Windows"
    import win32com.client

class UserInteractionRequired(Exception):
    print "UserInteractionRequired() exception"
    pass

class UserFeedback(Exception):
   INFO = 0
   WARN = 1
   ERROR = 2

   def __init__(self, msg, details, level):
       Exception.__init__(self, msg)
       self.level = level
       self.details = details
       self.msg = msg

class ITUNES(DevicePlugin):
    name = 'Apple device interface'
    gui_name = 'Apple device'
    icon = I('devices/ipad.png')
    description    = _('Communicate with iBooks through iTunes.')
    supported_platforms = ['windows','osx']
    author = 'GRiker'

    OPEN_FEEDBACK_MESSAGE = _('Apple device detected, launching iTunes')

    FORMATS = ['epub']

    VENDOR_ID = [0x05ac]
    # Product IDs:
    #  0x129a:iPad
    #  0x1292:iPhone 3G
    PRODUCT_ID = [0x129a,0x1292]
    BCD = [0x01]

    # Properties
    cached_books = {}
    iTunes= None
    path_template = 'iTunes/%s - %s.epub'
    presync = True
    purge_list = None
    sources = None
    update_msg = None
    update_needed = False
    use_thumbnail_as_cover = False
    verbose = True


    # Public methods

    def add_books_to_metadata(self, locations, metadata, booklists):
        '''
        Add locations to the booklists. This function must not communicate with
        the device.
        @param locations: Result of a call to L{upload_books}
        @param metadata: List of MetaInformation objects, same as for
        :method:`upload_books`.
        @param booklists: A tuple containing the result of calls to
                                (L{books}(oncard=None), L{books}(oncard='carda'),
                                L{books}(oncard='cardb')).
        '''
        print "ITUNES.add_books_to_metadata()"

        self._dump_booklist(booklists[0])
        # Delete any obsolete copies of the book from the booklist
        if self.purge_list:
            if self.verbose:
                print " purging updated books"
            for library_id in self.purge_list:
                for i,book in enumerate(booklists[0]):
                    if book.library_id == library_id:
                        booklists[0].pop(i)
            self.purge_list = []

        # Add new books to booklists[0]
        for new_book in locations[0]:
            booklists[0].append(new_book)
        self._dump_booklist(booklists[0])

    def books(self, oncard=None, end_session=True):
        """
        Return a list of ebooks on the device.
        @param oncard:  If 'carda' or 'cardb' return a list of ebooks on the
                        specific storage card, otherwise return list of ebooks
                        in main memory of device. If a card is specified and no
                        books are on the card return empty list.
        @return: A BookList.

        Implementation notes:
        iTunes does not sync purchased books, they are only on the device.  They are visible, but
        they are not backed up to iTunes.  Since calibre can't manage them, don't show them in the
        list of device books.

        """
        print "ITUNES:books(oncard=%s)" % oncard

        if not oncard:
            # Fetch a list of books from iPod device connected to iTunes
            if isosx:

                # Fetch Library|Books
                library_books = self._get_library_books()

                if 'iPod' in self.sources:
                    device = self.sources['iPod']
                    if 'Books' in self.iTunes.sources[device].playlists.name():
                        booklist = BookList()
                        cached_books = {}
                        device_books = self._get_device_books()
                        for book in device_books:
                            this_book = Book(book.name(), book.artist())
                            this_book.path = self.path_template % (book.name(), book.artist())
                            this_book.datetime = parse_date(str(book.date_added())).timetuple()
                            this_book.db_id = None
                            this_book.device_collections = []
                            this_book.library_id = library_books[this_book.path] if this_book.path in library_books else None
                            this_book.size = book.size()
                            this_book.thumbnail = self._generate_thumbnail(book)

                            booklist.add_book(this_book, False)

                            cached_books[this_book.path] = {
                             'title':book.name(),
                             'author':book.artist(),
                             'lib_book':library_books[this_book.path] if this_book.path in library_books else None
                             }


                        if self.verbose:
                            print
                            print "%-40.40s %-12.12s" % ('Device Books','In Library')
                            print "%-40.40s %-12.12s" % ('------------','----------')

                            for cp in cached_books.keys():
                                print "%-40.40s %6.6s" % (cached_books[cp]['title'], 'yes' if cached_books[cp]['lib_book'] else ' no')
                            print
                        self.cached_books = cached_books
                        return booklist
                    else:
                        # No books installed on this device
                        return []
        else:
            return []

    def can_handle(self, device_info, debug=False):
        '''
        Unix version of :method:`can_handle_windows`

        :param device_info: Is a tupe of (vid, pid, bcd, manufacturer, product,
        serial number)

        Confirm that:
            - iTunes is running
            - there is an iPod-type device connected
        This gets called first when the device fingerprint is read, so it needs to
        instantiate iTunes if necessary
        This gets called ~1x/second while device fingerprint is sensed
        '''

        if isosx:
            if self.iTunes:
                # Check for connected book-capable device
                names = [s.name() for s in self.iTunes.sources()]
                kinds = [str(s.kind()).rpartition('.')[2] for s in self.iTunes.sources()]
                self.sources = sources = dict(zip(kinds,names))
                if 'iPod' in sources:
                    if self.verbose:
                        sys.stdout.write('.')
                        sys.stdout.flush()
                    return True
                else:
                    if self.verbose:
                        print "ITUNES.can_handle(): device ejected"
                    return False
            else:
                # can_handle() is called once before open(), so need to return True
                # to keep things going
                print "ITUNES:can_handle(): iTunes not yet instantiated"
                return True

    def can_handle_windows(self, device_id, debug=False):
        '''
        Optional method to perform further checks on a device to see if this driver
        is capable of handling it. If it is not it should return False. This method
        is only called after the vendor, product ids and the bcd have matched, so
        it can do some relatively time intensive checks. The default implementation
        returns True. This method is called only on windows. See also
        :method:`can_handle`.

        :param device_info: On windows a device ID string. On Unix a tuple of
        ``(vendor_id, product_id, bcd)``.
        '''
        print "ITUNES:can_handle_windows()"
        return True

    def card_prefix(self, end_session=True):
        '''
        Return a 2 element list of the prefix to paths on the cards.
        If no card is present None is set for the card's prefix.
        E.G.
        ('/place', '/place2')
        (None, 'place2')
        ('place', None)
        (None, None)
        '''
        print "ITUNES:card_prefix()"
        return (None,None)

    def config_widget(cls):
        '''
        Should return a QWidget. The QWidget contains the settings for the device interface
        '''
        raise NotImplementedError()

    def delete_books(self, paths, end_session=True):
        '''
        Delete books at paths on device.
        iTunes doesn't let us directly delete a book on the device.
        If the requested paths are deletable (i.e., it's in the Library|Books list),
        delete the paths from the library, then update iPad

        '''
        undeletable_titles = []
        for path in paths:
            if self.cached_books[path]['lib_book']:
                if self.verbose:
                    print "ITUNES:delete_books(): Deleting '%s' from iTunes library" % (path)
                self._remove_iTunes_dir(self.cached_books[path])
                self.iTunes.delete(self.cached_books[path]['lib_book'])
                self.update_needed = True
                self.update_msg = "Deleted books from device"

            else:
                undeletable_titles.append(self.cached_books[path]['title'])

        if undeletable_titles:
            raise UserFeedback(_('You cannot delete purchased books. To do so delete them from the device itself. The books that could not be deleted are:'), details='\n'.join(undeletable_titles), level=UserFeedback.WARN)

    def eject(self):
        '''
        Un-mount / eject the device from the OS. This does not check if there
        are pending GUI jobs that need to communicate with the device.
        '''
        if self.verbose:
            print "ITUNES:eject(): ejecting '%s'" % self.sources['iPod']
        self.iTunes.eject(self.sources['iPod'])
        self.iTunes = None
        self.sources = None

    def free_space(self, end_session=True):
        """
        Get free space available on the mountpoints:
          1. Main memory
          2. Card A
          3. Card B

        @return: A 3 element list with free space in bytes of (1, 2, 3). If a
        particular device doesn't have any of these locations it should return -1.
        """
        print "ITUNES:free_space()"

        free_space = 0
        if isosx:
            if 'iPod' in self.sources:
                connected_device = self.sources['iPod']
                free_space = self.iTunes.sources[connected_device].free_space()

        return (free_space,-1,-1)

    def get_device_information(self, end_session=True):
        """
        Ask device for device information. See L{DeviceInfoQuery}.
        @return: (device name, device version, software version on device, mime type)
        """
        print "ITUNES:get_device_information()"

        return ('iPad','hw v1.0','sw v1.0', 'mime type')

    def get_file(self, path, outfile, end_session=True):
        '''
        Read the file at C{path} on the device and write it to outfile.
        @param outfile: file object like C{sys.stdout} or the result of an C{open} call
        '''
        raise NotImplementedError()

    def open(self):
        '''
        Perform any device specific initialization. Called after the device is
        detected but before any other functions that communicate with the device.
        For example: For devices that present themselves as USB Mass storage
        devices, this method would be responsible for mounting the device or
        if the device has been automounted, for finding out where it has been
        mounted. The base class within USBMS device.py has a implementation of
        this function that should serve as a good example for USB Mass storage
        devices.
        '''

        if isosx:
            # Launch iTunes if not already running
            if self.verbose:
                print "ITUNES:open(): Instantiating iTunes"

            # Instantiate iTunes
            running_apps = appscript.app('System Events')
            if not 'iTunes' in running_apps.processes.name():
                if self.verbose:
                    print "ITUNES:open(): Launching iTunes"
                self.iTunes = iTunes= appscript.app('iTunes', hide=True)
                iTunes.run()
                if self.verbose:
                    print "%s - %s (launched)" % (self.iTunes.name(), self.iTunes.version())
            else:
                self.iTunes = appscript.app('iTunes')
                if self.verbose:
                    print " %s - %s (already running)" % (self.iTunes.name(), self.iTunes.version())

            # Init the iTunes source list
            names = [s.name() for s in self.iTunes.sources()]
            kinds = [str(s.kind()).rpartition('.')[2] for s in self.iTunes.sources()]
            self.sources = sources = dict(zip(kinds,names))

            # Check to see if Library|Books out of sync with Device|Books
            if 'iPod' in self.sources and self.presync:
                lb_count = len(self._get_library_books())
                db_count = len(self._get_device_books())
                pb_count = len(self._get_purchased_book_ids())
                if db_count != lb_count + pb_count:
                    if self.verbose:
                        print "ITUNES.open(): pre-syncing iTunes with device"
                        print " Library|Books         : %d" % len(self._get_library_books())
                        print " Devices|iPad|Books    : %d" % len(self._get_device_books())
                        print " Devices|iPad|Purchased: %d" % len(self._get_purchased_book_ids())
                    self._update_device(msg="Presyncing iTunes with device, mismatched book count")
            else:
                if self.verbose:
                    print "Skipping pre-sync check"

    def post_yank_cleanup(self):
        '''
        Called if the user yanks the device without ejecting it first.
        '''
        raise NotImplementedError()

    def remove_books_from_metadata(self, paths, booklists):
        '''
        Remove books from the metadata list. This function must not communicate
        with the device.
        @param paths: paths to books on the device.
        @param booklists:  A tuple containing the result of calls to
                                (L{books}(oncard=None), L{books}(oncard='carda'),
                                L{books}(oncard='cardb')).
        '''
        print "ITUNES.remove_books_from_metadata():"
        for path in paths:
            if self.cached_books[path]['lib_book']:
                # Remove from the booklist
                for i,book in enumerate(booklists[0]):
                    if book.path == path:
                        print " removing '%s' from calibre booklist, index: %d" % (path, i)
                        booklists[0].pop(i)
                        break

                # Remove from cached_books
                print " Removing '%s' from self.cached_books" % path
                self.cached_books.pop(path)

            else:
                print " skipping purchased book, can't remove via automation interface"

    def reset(self, key='-1', log_packets=False, report_progress=None,
            detected_device=None) :
        """
        :key: The key to unlock the device
        :log_packets: If true the packet stream to/from the device is logged
        :report_progress: Function that is called with a % progress
                                (number between 0 and 100) for various tasks
                                If it is called with -1 that means that the
                                task does not have any progress information
        :detected_device: Device information from the device scanner
        """
        print "ITUNE.reset()"

    def save_settings(cls, settings_widget):
        '''
        Should save settings to disk. Takes the widget created in config_widget
        and saves all settings to disk.
        '''
        raise NotImplementedError()

    def set_progress_reporter(self, report_progress):
        '''
        @param report_progress: Function that is called with a % progress
                                (number between 0 and 100) for various tasks
                                If it is called with -1 that means that the
                                task does not have any progress information
        '''
        print "ITUNES:set_progress_reporter()"

    def settings(cls):
        '''
        Should return an opts object. The opts object should have one attribute
        `format_map` which is an ordered list of formats for the device.
        '''
        print "ITUNES.settings()"
        klass = cls if isinstance(cls, type) else cls.__class__
        c = Config('device_drivers_%s' % klass.__name__, _('settings for device drivers'))
        c.add_opt('format_map', default=cls.FORMATS,
            help=_('Ordered list of formats the device will accept'))
        return c.parse()

    def sync_booklists(self, booklists, end_session=True):
        '''
        Update metadata on device.
        @param booklists: A tuple containing the result of calls to
                                (L{books}(oncard=None), L{books}(oncard='carda'),
                                L{books}(oncard='cardb')).
        '''
        print "ITUNES:sync_booklists():"
        if self.update_needed:
            self._update_device(msg=self.update_msg)
            self.update_needed = False

    def total_space(self, end_session=True):
        """
        Get total space available on the mountpoints:
            1. Main memory
            2. Memory Card A
            3. Memory Card B

        @return: A 3 element list with total space in bytes of (1, 2, 3). If a
        particular device doesn't have any of these locations it should return 0.
        """
        if self.verbose:
            print "ITUNES:total_space()"
        capacity = 0
        if isosx:
            if 'iPod' in self.sources:
                connected_device = self.sources['iPod']
                capacity = self.iTunes.sources[connected_device].capacity()

        return (capacity,-1,-1)


    def upload_books(self, files, names, on_card=None, end_session=True,
                     metadata=None):
        '''
        Upload a list of books to the device. If a file already
        exists on the device, it should be replaced.
        This method should raise a L{FreeSpaceError} if there is not enough
        free space on the device. The text of the FreeSpaceError must contain the
        word "card" if C{on_card} is not None otherwise it must contain the word "memory".
        :files: A list of paths and/or file-like objects.
        :names: A list of file names that the books should have
        once uploaded to the device. len(names) == len(files)
        :return: A list of 3-element tuples. The list is meant to be passed
        to L{add_books_to_metadata}.
        :metadata: If not None, it is a list of :class:`MetaInformation` objects.
        The idea is to use the metadata to determine where on the device to
        put the book. len(metadata) == len(files). Apart from the regular
        cover (path to cover), there may also be a thumbnail attribute, which should
        be used in preference. The thumbnail attribute is of the form
        (width, height, cover_data as jpeg).
        '''
        if False:
            print
            print "ITUNES.upload_books():"
            for file in files:
                print "        file: %s" % file
            print

            print "names:"
            for name in names:
                print "        name: %s" % name
            print

            print "metadata:"
            print dir(metadata[0])
            for md in metadata:
                print "       title: %s" % md.title
                print "  title_sort: %s" % md.title_sort
                print "      author: %s" % md.author[0]
                print " author_sort: %s" % md.author_sort
                print "        tags: %s" % md.tags
                print "      rating: %s" % md.rating
                print "       cover: %s" % md.cover
                #print "  cover_data: %s" % repr(md.cover_data)
                #print "thumbnail: %s" % repr(md.thumbnail)

                print
            print

        #print "thumbnail: width: %d height: %d" % (metadata[0].thumbnail[0], metadata[0].thumbnail[1])
        #self._hexdump(metadata[0].thumbnail[2])

        new_booklist = []
        self.purge_list = []

        if isosx:

            for (i,file) in enumerate(files):
                path = self.path_template % (metadata[i].title, metadata[i].author[0])

                # Delete existing from Library|Books, add to self.purge_list
                # for deletion from booklist[0] during add_books_to_metadata
                if path in self.cached_books:
                    self.purge_list.append(self.cached_books[path])

                    if self.verbose:
                        print " deleting existing '%s' at\n %s" % (path,self.cached_books[path]['lib_book'])
                    self._remove_iTunes_dir(self.cached_books[path])
                    self.iTunes.delete(self.cached_books[path]['lib_book'])

                # Add to iTunes Library|Books
                added = self.iTunes.add(appscript.mactypes.File(files[i]))

                thumb = None
                if self.use_thumbnail_as_cover:
                    # Use thumbnail data as artwork
                    added.artworks[1].data_.set(metadata[i].thumbnail[2])
                    thumb = metadata[i].thumbnail[2]
                else:
                    # Use cover data as artwork
                    cover_data = open(metadata[i].cover,'rb')
                    added.artworks[1].data_.set(cover_data.read())

                    # Resize for thumb
                    width = metadata[i].thumbnail[0]
                    height = metadata[i].thumbnail[1]
                    im = PILImage.open(metadata[i].cover)
                    im = im.resize((width, height), PILImage.ANTIALIAS)
                    of = cStringIO.StringIO()
                    im.convert('RGB').save(of, 'JPEG')
                    thumb = of.getvalue()


                # Create a new Book
                this_book = Book(metadata[i].title, metadata[i].author[0])
                this_book.datetime = parse_date(str(added.date_added())).timetuple()
                this_book.db_id = None
                this_book.device_collections = []
                this_book.library_id = added
                this_book.path = path
                this_book.size = added.size()  # GwR this is wrong, needs to come from device or fake it
                this_book.thumbnail = thumb
                this_book.iTunes_id = added

                new_booklist.append(this_book)

                # Flesh out the iTunes metadata
                added.comment.set("added by calibre %s" % strftime('%Y-%m-%d %H:%M:%S'))
                added.rating.set(metadata[i].rating*10)
                added.sort_artist.set(metadata[i].author_sort)
                added.sort_name.set(this_book.title_sorter)
                # Set genre from metadata
                # iTunes grabs the first dc:subject from the opf metadata,
                # But we can manually override
                # added.genre.set(metadata[i].tags[0])

                # Add new_book to self.cached_paths
                self.cached_books[this_book.path] = {
                 'title': this_book.title,
                 'author': this_book.author,
                 'lib_book': this_book.library_id
                 }


            # Tell sync_booklists we need a re-sync
            self.update_needed = True
            self.update_msg = "Added books to device"

        return (new_booklist, [], [])

    # Private methods
    def _dump_booklist(self,booklist, header="booklists[0]"):
        print
        print header
        print "%s" % ('-' * len(header))
        for i,book in enumerate(booklist):
            print "%2d %-25.25s %s" % (i,book.title, book.library_id)
        print

    def _hexdump(self, src, length=16):
        # Diagnostic
        FILTER=''.join([(len(repr(chr(x)))==3) and chr(x) or '.' for x in range(256)])
        N=0; result=''
        while src:
           s,src = src[:length],src[length:]
           hexa = ' '.join(["%02X"%ord(x) for x in s])
           s = s.translate(FILTER)
           result += "%04X   %-*s   %s\n" % (N, length*3, hexa, s)
           N+=length
        print result

    def _get_library_books(self):
        lib = self.iTunes.sources['library']
        library_books = {}
        if 'Books' in lib.playlists.name():
            lib_books = lib.playlists['Books'].file_tracks()
            for book in lib_books:
                path = self.path_template % (book.name(), book.artist())
                library_books[path] = book
        return library_books

    def _get_device_books(self):
        if 'iPod' in self.sources:
            device = self.sources['iPod']
            device_books = []
            if 'Books' in self.iTunes.sources[device].playlists.name():
                return self.iTunes.sources[device].playlists['Books'].file_tracks()

    def _generate_thumbnail(self, book):
        '''
        Convert iTunes artwork to thumbnail
        Cache generated thumbnails
        '''
        print "ITUNES._generate_thumbnail()"

        try:
            n = len(book.artworks())
            print "Library '%s' has %d artwork items" % (book.name(),n)
#             for art in book.artworks():
#                 print "description: %s" % art.description()
#                 if str(art.description()) == 'calibre_thumb':
#                     print "using cached thumb"
#                     return art.raw_data().data


            # Resize the cover
            data = book.artworks[1].raw_data().data
            #self._hexdump(data[:256])
            im = PILImage.open(cStringIO.StringIO(data))
            scaled, width, height = fit_image(im.size[0],im.size[1], 60, 80)
            im = im.resize((int(width),int(height)), PILImage.ANTIALIAS)
            thumb = cStringIO.StringIO()
            im.convert('RGB').save(thumb,'JPEG')

            # Cache the tagged thumb
#             print "caching thumb"
#             book.artworks[n+1].data_.set(thumb.getvalue())
#             book.artworks[n+1].description.set(u'calibre_thumb')
            return thumb.getvalue()
        except:
            print "Can't generate thumb for '%s'" % book.name()
            return None

    def _get_purchased_book_ids(self):
        if 'iPod' in self.sources:
            device = self.sources['iPod']
            purchased_book_ids = []
            if 'Purchased' in self.iTunes.sources[device].playlists.name():
                return [pb.database_ID() for pb in self.iTunes.sources[device].playlists['Purchased'].file_tracks()]

    def _remove_iTunes_dir(self, cached_book):
        '''
        iTunes does not delete books from storage when removing from database
        '''
        storage_path = os.path.split(cached_book['lib_book'].location().path)
        if self.verbose:
            print "ITUNES._remove_iTunes_dir():"
            print " removing storage_path: %s" % storage_path[0]
        shutil.rmtree(storage_path[0])


    def _update_device(self, msg='', wait=True):
        '''
        This probably needs a job spinner
        '''
        if self.verbose:
            print "ITUNES:_update_device(): %s" % msg
        self.iTunes.update()

        if wait:
            # This works if iTunes has books not yet synced to iPad.
            print "Waiting for iPad sync to complete ...",
            while len(self._get_device_books()) != (len(self._get_library_books()) + len(self._get_purchased_book_ids())):
                sys.stdout.write('.')
                sys.stdout.flush()
                time.sleep(2)
            print


class BookList(list):
    '''
    A list of books. Each Book object must have the fields:
      1. title
      2. authors
      3. size (file size of the book)
      4. datetime (a UTC time tuple)
      5. path (path on the device to the book)
      6. thumbnail (can be None) thumbnail is either a str/bytes object with the
         image data or it should have an attribute image_path that stores an
         absolute (platform native) path to the image
      7. tags (a list of strings, can be empty).
    '''

    __getslice__ = None
    __setslice__ = None

    def __init__(self):
        pass

    def supports_collections(self):
        ''' Return True if the the device supports collections for this book list. '''
        return False

    def add_book(self, book, replace_metadata):
        '''
        Add the book to the booklist. Intent is to maintain any device-internal
        metadata. Return True if booklists must be sync'ed
        '''
        print "adding %s" % book
        self.append(book)

    def remove_book(self, book):
        '''
        Remove a book from the booklist. Correct any device metadata at the
        same time
        '''
        raise NotImplementedError()

    def get_collections(self, collection_attributes):
        '''
        Return a dictionary of collections created from collection_attributes.
        Each entry in the dictionary is of the form collection name:[list of
        books]

        The list of books is sorted by book title, except for collections
        created from series, in which case series_index is used.

        :param collection_attributes: A list of attributes of the Book object
        '''
        return {}

class Book(MetaInformation):
    '''
    A simple class describing a book in the iTunes Books Library.
    Q's:
    - Should thumbnail come from calibre if available?
    - See ebooks.metadata.__init__ for all fields
    '''
    def __init__(self,title,author):

        MetaInformation.__init__(self, title, authors=[author])

    @dynamic_property
    def title_sorter(self):
        doc = '''String to sort the title. If absent, title is returned'''
        def fget(self):
            return re.sub('^\s*A\s+|^\s*The\s+|^\s*An\s+', '', self.title).rstrip()
        return property(doc=doc, fget=fget)
