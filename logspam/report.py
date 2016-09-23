# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from collections import Counter
from logspam.cli import BaseCommandLineArgs
from logspam.logs import (retrieve_test_logs, WarningInfo)
import re

class InvalidRegexException(Exception):
    pass

class WarningNotFoundException(Exception):
    pass

class Warnings(object):
    def __init__(self, repo, revision, platform,
                 cache_dir, use_cache, warning_re):
        self.repo = repo
        self.revision = revision
        self.platform = platform
        self.warning_re = warning_re

        if not cache_dir:
            cache_dir = "%s-%s-%s" % (repo, revision, platform)
        self.cache_dir = cache_dir

        files = retrieve_test_logs(repo, revision, platform,
                                   cache_dir, use_cache, warning_re)
        self.logs = [f for f in files if f]

        self.combined_warnings = Counter()
        for log in self.logs:
            self.combined_warnings.update(log.warnings)

    def top(self, warning_count, reverse=False):
        print "Top %d Warnings" % warning_count
        print "==============="
        most_common = self.combined_warnings.most_common()

        if reverse:
            warnings_list = most_common[:-warning_count:-1]
        else:
            warnings_list = most_common[:warning_count]

        for (warning, count) in warnings_list:
            print "%6d %s" % (count, warning)

        print "TOTAL WARNINGS: %d" % sum(self.combined_warnings.values())

    def details(self, warning, test_summary_count):
        # Sanity check the warning format.
        if not re.match(self.warning_re, warning):
            raise InvalidRegexException(
                "Provided warning %s does not match warning regex %s" %
                    (warning, self.warning_re))

        info = WarningInfo(warning, self.combined_warnings[warning])
        info.match_in_logs(self.cache_dir, self.logs)

        if not info.count:
            raise WarningNotFoundException(
                "Provided warning %s was not found" % warning)

        return info.details(
                self.repo, self.revision,
                self.platform, test_summary_count)


class ReportCommandLineArgs(BaseCommandLineArgs):
    @staticmethod
    def do_report(cmdline):
        warnings = Warnings(cmdline.repo, cmdline.revision, cmdline.platform,
                            cmdline.cache_dir, cmdline.use_cache,
                            cmdline.warning_re)

        if not cmdline.warning:
            warnings.top(cmdline.warning_count, cmdline.reverse)
        else:
            (summary, details) = warnings.details(cmdline.warning, cmdline.test_summary_count)
            print "\n".join([summary, "", details])

    def add_command(self, p):
       parser = p.add_parser('report')
       self.add_arguments(parser)
       parser.set_defaults(func=ReportCommandLineArgs.do_report)

    def add_arguments(self, p):
        """
        Adds report specific command-line args.
        """
        p.add_argument('revision',
                       help='Revision to retrieve logs for.')
        p.add_argument('warning', nargs='?',
                       help='Optional: The text of a warning you want the full details of.')

        super(ReportCommandLineArgs, self).add_arguments(p)

        p.add_argument('--repo', action='store', default='mozilla-central',
                       help='Repository the revision corresponds to. Default: mozilla-central')
        p.add_argument('--no-cache', action='store_false', default=True, dest='use_cache',
                       help='Redownload logs if already present.')
        p.add_argument('--cache-dir', action='store', default=None,
                       help='Directory to cache logs to. Default: <repo>-<revision>')
        p.add_argument('--warning-count', action='store', default=40, type=int,
                       help='Number of warnings to show in the default summary. Default: 40')
        p.add_argument('--test-summary-count', action='store', default=10, type=int,
                       help='Number of tests to list in warning summary mode. Default: 10')
        p.add_argument('--reverse', action='store_true', default=False,
                       help='Print the least common warnings instead.')
