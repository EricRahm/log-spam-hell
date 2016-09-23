# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

WARNING_RE='^WARNING'

class BaseCommandLineArgs(object):
    """
    Base for logspam cli command line arguments. Subcommands should derive from
    this class.
    """
    def add_arguments(self, p):
        """
        Adds command-line arguments for the given argparser.
        """
        p.add_argument('--platform', action='store', default='linux64',
                       help='Platform to get logs for. Default: linux64')
        p.add_argument('--warning-re', action='store', default=WARNING_RE,
                       help='Regex used to match lines. Can be used to match ' \
                            'debug messages that are not proper warnings.')
