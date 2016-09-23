# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import ConfigParser
import os
import requests
from logspam.report import (
        ReportCommandLineArgs,
        Warnings,
        WarningNotFoundException)


#BUGZILLA_API='https://landfill.bugzilla.org/bugzilla-5.0-branch/rest'
BUGZILLA_API='https://bugzilla.mozilla.org/rest'

class Bugzilla:
    """
    Super basic wrapper for the bugzilla api.
    """
    def __init__(self, host, api_key):
        self.host = host

        if not api_key:
            cfg = ConfigParser.ConfigParser()
            cfg.read(os.path.join(os.path.expanduser('~'), '.hgrc'))
            api_key = cfg.get('bugzilla', 'apikey')

        self.api_key = api_key

    def post(self, endpoint, data):
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

        r = requests.post("%s/%s?api_key=%s" % (self.host, endpoint, self.api_key),
                          json=data, headers=headers)
        #print r.headers
        #print r.text
        return r.json()

    def create_bug(self, summary, desc, component, product='Core', version='Trunk'):
        """
        Files a bug for the given warning.
        """

        # Future enhancements:
        # - Attempt to map a file to a component. There's some sort of mach
        #   support for this. See |mach file-info|.
        # - If warning was added recently ni? the person who added it, cc the
        #   reviewer.
        # - If warning was added long ago cc the person who added it.
        # - Generate a removal patch.

        r = self.post('bug', {
            'product': product,
            'component': component,
            'version': version,
            'summary': summary,
            'description': desc,
            'op_sys': 'All',
            'platform': 'All',
            'blocks': 'logspam'
        })

        return r

class FileCommandLineArgs(ReportCommandLineArgs):
    @staticmethod
    def do_file(cmdline):
        warnings = Warnings(cmdline.repo, cmdline.revision, cmdline.platform,
                            cmdline.cache_dir, cmdline.use_cache,
                            cmdline.warning_re)

        try:
            (summary, details) = warnings.details(cmdline.warning, cmdline.test_summary_count)
        except WarningNotFoundException:
            print "There are zero warnings matching %s" % cmdline.warning
            print "Not filing bug!"
            return

        try:
            bz = Bugzilla(BUGZILLA_API, cmdline.api_key)
        except Exception as e:
            print "I'm sorry, I couldn't guess your api key. Please " \
                  "specify it with --api_key"
            print e
            return

        result = bz.create_bug(
                summary, details, component=cmdline.component,
                product=cmdline.product)
        print "Filed bug %d" % result['id']

    def add_command(self, p):
       parser = p.add_parser('file')
       self.add_arguments(parser)
       parser.set_defaults(func=FileCommandLineArgs.do_file)

    def add_arguments(self, p):
        """
        Adds file specific command-line args.
        """
        super(FileCommandLineArgs, self).add_arguments(p)

        p.add_argument('--component', action='store', default=None,
                       required=True,
                       help='Component to file the bug in.')
        p.add_argument('--product', action='store', default='Core',
                       help='Product to file the bug in. Default: Core')
        p.add_argument('--api-key', action='store', default=None,
                       help='The API key to use when creating the bug. Default: extracted from .hgrc')
