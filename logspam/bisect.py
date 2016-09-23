# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from logspam.cli import BaseCommandLineArgs
from logspam.logs import retrieve_test_logs

from mozregression.bisector import (
    Bisector, Bisection, NightlyHandler, InboundHandler)
from mozregression.dates import parse_date
from mozregression.errors import DateFormatError
from mozregression.fetch_build_info import InboundInfoFetcher
from mozregression.fetch_configs import create_config
from mozregression.log import init_logger
from mozregression.test_runner import TestRunner

WARNING_RE='^WARNING'

class WarningBisector(object):
    def __init__(self, good, bad, platform, warning,
                 warning_limit, warning_re, ignore_lines):

        self.use_nightly = True
        try:
            self.good = parse_date(good)
            self.bad = parse_date(bad)
        except DateFormatError:
            # This hopefully a revision range. We can bypass nightly and
            # go directly to InboundHandler. That itself is a bit of a misnomer,
            # it will still bisect m-c builds, but by changeset range, not date
            # range.
            self.use_nightly = False
            self.good = good
            self.bad = bad

        test_runner = WarningTestRunner(
                warning, platform,
                ignore_lines=ignore_lines,
                warning_re=warning_re,
                warning_limit=warning_limit)

        # Convert the platform to a mozregression friendly version.
        # Also avoid overwriting the os module by *not* using |os| for a
        # variable name.
        (_os, bits) = re.match(r'([a-zA-Z]+)-?([0-9]+)?', platform).groups()
        if not bits:
            bits = 32

        if _os.startswith('win'):
            _os = 'win'

        self.fetch_config = create_config('firefox', _os, int(bits))
        # Hardcode to m-c for now.
        self.fetch_config.set_repo('mozilla-central')
        self.fetch_config.set_build_type('debug')

        self.bisector = Bisector(fetch_config, test_runner, None, False, None)

    def bisect(self):
        if not self.use_nightly:
            self.bisect_inbound(self.good, self.bad)

        handler = NightlyHandler(ensure_good_and_bad=True)
        result = self.bisector.bisect(handler, self.good, self.bad)
        if result == Bisection.FINISHED:
            print "Got as far as we can go bisecting nightlies..."
            handler.print_range()
            print "Switching bisection method to taskcluster"
            #fetch_config.set_repo(fetch_config.get_nightly_repo(handler.bad_date))

            self.bisect_inbound(handler.good_revision, handler.bad_revision)

        print "Done bisecting I guess"
        return

    def bisect_inbound(good_rev, bad_rev):
        # Remember, InboundHandler is just a changeset based bisector. It will
        # still potentially bisect m-c first.
        handler = InboundHandler()
        result = self.bisector.bisect(handler, good_rev, bad_rev, expand=0)
        if result == Bisection.FINISHED:
            print "No more m-c revisions :("
            handler.print_range()
            # Try switching over to the integration branch.
            if len(handler.build_range) == 2:
                result = handler.handle_merge()
                if result:
                    branch, good_rev, bad_rev = result
                    self.fetch_config.set_repo(branch)
                    self.bisect_inbound(good_rev, bad_rev)


class BisectCommandLineArgs(BaseCommandLineArgs):
    @staticmethod
    def do_bisect(args):
        print "do_bisect called"
        print args

    def add_command(self, p):
       parser = p.add_parser('bisect')
       self.add_arguments(parser)
       parser.set_defaults(func=BisectCommandLineArgs.do_bisect)

    def add_arguments(self, p):
        # TODO(ER): add a date/revision parser
        p.add_argument('good', action='store', default=None,
                       help='Last known good date. Will be validated.')
        p.add_argument('bad', action='store', default=None,
                       help='Last known bad date.')
        p.add_argument('warning', nargs='?',
                       help='The text of a warning you want the full details of.')

        super(BisectCommandLineArgs, self).add_arguments(p)

        p.add_argument('--ignore-lines', action='store_true', default=False,
                       help='Ignore line numbers when bisecting warnings. Useful if' \
                            ' the line number of the warning has changed. Not so ' \
                            'useful if there are a lot of similar warnings in the ' \
                            'file.')
        p.add_argument('--warning-limit', action='store', default=1000,
                       help='The threshold of warnings for going from good to ' \
                            'bad. Default: 1000.')


class WarningTestRunner(TestRunner):
    """
    TestRunner to use in conjunction with bisection.
    """
    def __init__(self, warning, platform='linux64', ignore_lines=False,
                 warning_re=WARNING_RE, warning_limit=1000):
        TestRunner.__init__(self)
        self.warning = warning
        self.warning_re = warning_re
        self.platform = platform
        self.ignore_lines = ignore_lines
        self.warning_limit = warning_limit

    def evaluate(self, build_info, allow_back=False):
        files = retrieve_test_logs(
                build_info.repo_name, build_info.changeset[:12],
                self.platform, warning_re=self.warning_re)

        # Somewhat arbitrary, but we need to make sure there are enough tests
        # run in order to make a reasonable evaluation of the amount of
        # warnings present.
        if len(files) < 100:
            # Tell the bisector to skip this build.
            print "Skipping build %s, not enough tests run" % build_info.changeset[:12]
            return 's'

        combined_warnings = Counter()
        for log in files:
            if log:
                combined_warnings.update(log.warnings)

        if self.ignore_lines:
            normalized = re.match(r'^(.*), line [0-9]+$', self.warning).group(1)

            total = 0
            for (k, v) in combined_warnings.iteritems():
                if k.startswith(normalized):
                    total += v
            print "%d - %s" % (total, normalized)
        else:
            total = combined_warnings[self.warning]
            print "%d - %s" % (total, self.warning)

        if total > self.warning_limit:
            return 'b'
        else:
            return 'g'

    def run_once(self, build_info):
        return 0 if self.evaluate(build_info) == 'g' else 1
