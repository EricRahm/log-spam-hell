# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import configparser
import json
import os
import requests
import subprocess

from logspam.report import (
        ReportCommandLineArgs,
        Warnings,
        WarningNotFoundException)


#BUGZILLA_API='https://landfill.bugzilla.org/bugzilla-5.0-branch/rest'
BUGZILLA_API='https://bugzilla.mozilla.org/rest'

def get_component_info(hgroot, path):
    p = subprocess.Popen([os.path.join(hgroot, 'mach'), 'file-info', 'bugzilla-component', '--format', 'json', path],
                         shell=False, cwd=hgroot, stdout=subprocess.PIPE)
    (out, err) = p.communicate()
    mappings = json.loads(out)
    return mappings[path]


class Bugzilla:
    """
    Super basic wrapper for the bugzilla api.
    """
    def __init__(self, host, api_key):
        self.host = host

        if not api_key:
            cfg = configparser.ConfigParser()
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
            'blocks': 'logspam',
            'type': 'defect'
        })

        return r

class FileCommandLineArgs(ReportCommandLineArgs):
    @staticmethod
    def do_file(cmdline):
        warnings = Warnings(cmdline.repo, cmdline.revision, cmdline.platform,
                            cmdline.cache_dir, cmdline.use_cache,
                            cmdline.warning_re)

        try:
            (summary, details, path) = warnings.details(cmdline.warning, cmdline.test_summary_count)
        except WarningNotFoundException:
            print("There are zero warnings matching %s" % cmdline.warning)
            print("Not filing bug!")
            return

        try:
            bz = Bugzilla(BUGZILLA_API, cmdline.api_key)
        except Exception as e:
            print("I'm sorry, I couldn't guess your api key. Please " \
                  "specify it with --api_key")
            print(e)
            return

        if not cmdline.component:
            # Try to figure it out.
            try:
                (product, component) = get_component_info(cmdline.hgroot, path)
            except Exception as e:
                print("Couldn't figure out the component for '%s'. Please " \
                      "specify it with --component" % path)
                return

            print("Guessed %s :: %s - %s" % (product, component, path))
        else:
            product = cmdline.product
            component = cmdline.component

        result = bz.create_bug(
                summary, details, component=component,
                product=product)
        print(result)
        print("Filed bug %d" % result['id'])

    def add_command(self, p):
       parser = p.add_parser('file',
            help='Files a logspam bug in bugzilla for the given warning.')
       self.add_arguments(parser)
       parser.set_defaults(func=FileCommandLineArgs.do_file)

    def add_arguments(self, p):
        """
        Adds file specific command-line args.
        """
        super(FileCommandLineArgs, self).add_arguments(p)

        g = p.add_mutually_exclusive_group(required=True)
        g.add_argument('--component', action='store', default=None,
                       help='Component to file the bug in.')
        g.add_argument('--hgroot', action='store', default=None,
                       help='local mozilla repo to use for mapping components')

        p.add_argument('--product', action='store', default='Core',
                       help='Product to file the bug in. Default: Core')
        p.add_argument('--api-key', action='store', default=None,
                       help='The API key to use when creating the bug. Default: extracted from .hgrc')

