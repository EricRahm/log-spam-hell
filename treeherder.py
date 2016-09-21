#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from argparse import ArgumentParser
from collections import Counter
import ConfigParser
from functools import partial
import hashlib
import json
from multiprocessing import Pool
import os
import pprint
import re
import shutil
import datetime

import requests
from thclient import TreeherderClient

from mozregression.bisector import (Bisector, Bisection, NightlyHandler, InboundHandler)
from mozregression.fetch_build_info import InboundInfoFetcher
from mozregression.test_runner import TestRunner


DEBUG_OPTIONHASH = '32faaecac742100f7753f0c1d0aa0add01b4046b'

BRANCH_MAP = {
    'b2g-inbound': 'integration/b2g-inbound',
    'fx-team': 'integration/fx-team',
    'mozilla-inbound': 'integration/mozilla-inbound'
}

#BUGZILLA_API='https://landfill.bugzilla.org/bugzilla-5.0-branch/rest'
BUGZILLA_API='https://bugzilla.mozilla.org/rest'

WARNING_RE='^WARNING'

def normalize_line(line):
    """
    Normalizes the given line to make comparisons easier. Removes:
      - timestamps
      - pids
      - trims file paths
      - stuff that looks like a pointer address
    """
    # taskcluster prefixing:
    #   [task 2016-09-20T11:09:35.539828Z] 11:09:35
    line = re.sub(r'^\[task[^\]]+\]\s', '', line)
    line = re.sub(r'^[0-9:]+\s+INFO\s+-\s+', '', line)
    line = re.sub(r'^PROCESS \| [0-9]+ \| ', '', line)
    line = re.sub(r'\[(Child|Parent|GMP|NPAPI)?\s?[0-9]+\]', '', line)
    line = re.sub(r'/home/worker/workspace/build/src/', '', line)
    # Attempt buildbot paths, ie:
    #  c:/builds/moz2_slave/m-cen-w32-d-000000000000000000/build/src/
    line = re.sub(r'([a-z]:)?/builds/[^/]+/[^/]+/build/src/', '', line)
    #blah=1caa2c00
    line = re.sub(r'=[a-z0-9]+', '=NNNNNN', line)
    line = line.strip()

    return line


class Bugzilla:
    """
    Super basic wrapper for the bugzilla api.
    """
    def __init__(self, host, api_key):
        self.host = host
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


class WarningInfo:
    """
    Provides details for a warning.
    """
    def __init__(self, warning_text, warning_count):
        self.full_text = warning_text
        self.count = warning_count

        # Extract the warning text, file name, and line number.
        m = re.match(r'.*WARNING: (.*)[:,] file ([^,]+), line ([0-9]+).*', warning_text)
        if m:
            (self.text, self.file, self.line) = m.group(1, 2, 3)
        else:
            self.text = warning_text
            self.file = "none"
            self.line = 0

        self.jobs = Counter()
        self.tests = Counter()

    def match_in_logs(self, cache_dir, parsed_logs):
        """
        Finds the number of warnings in each test job and the number of
        warnings per test and updates |jobs| and |tests|.
        """
        warning_re = re.compile(re.escape(self.full_text))

        for log in parsed_logs:
            count = log.warnings[self.full_text]
            if not count:
                continue

            self.jobs[log.job_name] = count

            curr_test = None
            e10s_prefix = '[e10s] ' if 'e10s' in log.job_name else '       '

            with open(os.path.join(cache_dir, log.fname), 'r') as f:
                for line in f:
                    # Check if this is the beginning of a new test.
                    m = re.search('TEST-START \| (.*)', line)
                    if m:
                        curr_test = e10s_prefix + m.group(1)

                    # See if the warning is present in the current line.
                    try:
                        if curr_test and warning_re.search(line):
                            self.tests[curr_test] += 1
                    except:
                        # For some reason doing |self.full_text in line| blows
                        # up when unicode strings are in the line. For now
                        # switch to regex which hopefully isn't too slow.
                        print "Can't read line:\n  %s" % line

            if not curr_test:
                print "No test names matched?"
            elif not self.tests:
                print "No warnings matched?"

    def details(self, repo, revision, platform='linux64', test_count=10):
        """
        Provides details for the warning suitable for filing in bugzilla.

        Returns a tuple of the summary for a bug and the details for comment #0
        of the bug.
        """
        rounded = int(round(self.count / 100.0)) * 100
        summary = "%s instances of \"%s\" emitted from %s " \
                  "during %s debug testing" % (
                      '{:,}'.format(rounded),
                      self.text,
                      self.file,
                      platform)

        details = []
        details.append("> %d %s" % (self.count, self.full_text))
        details.append("")
        details.append("This warning [1] shows up in the following test suites:")
        details.append("")
        for (job, count) in self.jobs.most_common():
            details.append("> %6d - %s" % (count, job))
        details.append("")
        details.append("It shows up in %d tests. A few of the most prevalent:" % len(self.tests))
        details.append("")
        for (test, count) in self.tests.most_common(test_count):
            details.append("> %6d - %s" % (count, test))
        details.append("")
        details.append("[1] https://hg.mozilla.org/%s/annotate/%s/%s#l%d" % (
                BRANCH_MAP.get(repo, repo), revision, self.file, int(self.line)))

        return (summary, "\n".join(details))


class ParsedLog:
    """
    Represents a log file that was downloaded and processed.
    """
    def __init__(self, url, job_name, file_name=None):
        self.url = url
        self.job_name = job_name
        if not file_name:
            self.fname = os.path.basename(job_name.replace(' ', '_') + '.log')
        else:
            self.fname = file_name

        self.warnings = Counter()

    def _download_file(self, dest, warning_re):
        r = requests.get(self.url, stream=True)
        with open(dest, 'w') as f:
            for x in r.iter_lines():
                if x:
                    line = normalize_line(x)
                    self.add_warning(line, warning_re)
                    f.write(line + '\n')

    def download(self, cache_dir, warning_re):
        """
        Downloads the log file and normalizes it. Warnings are also
        accumulated.
        """
        success = True
        # Check if we can bypass downloading first.
        dest = os.path.join(cache_dir, self.fname)
        if os.path.exists(dest):
            with open(dest, 'r') as f:
                for x in f:
                    self.add_warning(x.rstrip(), warning_re)
        else:
            success = False
            for i in range(5):
                try:
                    self._download_file(dest, warning_re)
                    success = True
                    break
                except requests.exceptions.ConnectionError:
                    # TODO(ER): Maybe nuke dest?
                    self.warnings.clear()
                    pass

        return success

    def add_warning(self, line, match_re=WARNING_RE):
        """
        Adds the line to the set of warnings if it contains a warning.
        """
        if re.search(match_re, line):
            self.warnings[line] += 1

    def to_json(self):
        """
        Creates a json representation of this object.
        """
        return {
            'url': self.url,
            'job_name': self.job_name,
            'fname': self.fname,
            'warnings': dict(self.warnings)
        }


def download_log(job, dest, repo, revision, warning_re):
    """
    Downloads the log file for the given job.

    Returns the log file name.
    """
    job_id = job['id']
    job_name = job['job_type_name']
    if job['job_type_symbol']:
        job_name += " " + job['job_type_symbol'] # Needed for jobs without unique names

    print "Downloading log for %s %d" % (job_name, job_id)

    client = TreeherderClient(protocol='https', host='treeherder.mozilla.org')
    job_log = client.get_job_log_url(repo, job_id=job_id)

    try:
        job_log_url = job_log[0]['url']
    except:
        print "Couldn't determine job log URL for %s" % job_name
        return None

    parsed_log = ParsedLog(url=job_log_url, job_name=job_name)
    if not parsed_log.download(dest, warning_re):
        print "Couldn't download log URL for %s" % job_name
        return None

    return parsed_log


class CustomEncoder(json.JSONEncoder):
    """
    Custom JSON encoder that handles ParsedLog objects.
    """
    def default(self, obj):
        if isinstance(obj, ParsedLog):
            return obj.to_json()
        return json.JSONEncoder.default(self, obj)


def cache_file_path(cache_dir, warning_re):
    """
    Generates the cache file name.
    """
    if warning_re != WARNING_RE:
        warning_md5 = hashlib.md5(warning_re).hexdigest()
        return os.path.join(cache_dir, "results.%s.json" % warning_md5)
    else:
        return os.path.join(cache_dir, "results.json")


def cache_results(dest, parsed_logs, warning_re):
    """
    Caches the parsed results in a json file.
    """
    fname = cache_file_path(dest, warning_re)
    with open(fname, 'w') as f:
        json.dump(parsed_logs, f, cls=CustomEncoder)


def read_cached_results(cache_dir, warning_re):
    """
    Reads the cached results from a previous run.
    """
    fname = cache_file_path(cache_dir, warning_re)
    print "Reading cache from %s" % fname
    parsed_logs = []
    with open(fname, 'r') as f:
        raw_list = json.load(f)
        for x in raw_list:
            log = ParsedLog(x['url'], x['job_name'], x['fname'])
            log.warnings.update(x['warnings'])
            parsed_logs.append(log)

    return parsed_logs


def add_arguments(p):
    """
    Adds command-line arguments to the given argparser.
    """
    p.add_argument('--repo', action='store', default='mozilla-central',
                   help='Repository the revision corresponds to. Default: mozilla-central')
    p.add_argument('revision',
                   help='Revision to retrieve logs for.')
    p.add_argument('warning', nargs='?',
                   help='Optional: The text of a warning you want the full details of.')
    p.add_argument('--no-cache', action='store_false', default=True, dest='use_cache',
                   help='Redownload logs if already present.')
    p.add_argument('--cache-dir', action='store', default=None,
                   help='Directory to cache logs to. Default: <repo>-<revision>')
    p.add_argument('--warning-count', action='store', default=40, type=int,
                   help='Number of warnings to show in the default summary. Default: 40')
    p.add_argument('--test-summary-count', action='store', default=10, type=int,
                   help='Number of tests to list in warning summary mode. Default: 10')
    p.add_argument('--platform', action='store', default='linux64',
                   help='Platform to get logs for. Default: linux64')
    p.add_argument('--reverse', action='store_true', default=False,
                   help='Print the least common warnings instead.')
    p.add_argument('--create-bug', action='store_true', default=False,
                   help='Create a new bug for the specified warning.')
    p.add_argument('--component', action='store', default=None,
                   help='Component to file the bug in.')
    p.add_argument('--product', action='store', default='Core',
                   help='Product to file the bug in. Default: Core')
    p.add_argument('--api-key', action='store', default=None,
                   help='The API key to use when creating the bug. Default: extracted from .hgrc')
    p.add_argument('--warning-re', action='store', default=WARNING_RE,
                   help='Regex used to match lines. Can be used to match ' \
                        'debug messages that are not proper warnings.')
    p.add_argument('--bisect', action='store', default=None,
                   help='Date to bisect from.')
    p.add_argument('--ignore-lines', action='store_true', default=False,
                   help='Ignore line numbers when bisecting warnings. Useful if' \
                        ' the line number of the warning has changed. Not so ' \
                        'useful if there are a lot of similar warnings in the ' \
                        'file.')


class WarningTestRunner(TestRunner):
    """
    TestRunner to use in conjunction with bisection.
    """
    def __init__(self, warning, platform='linux64', ignore_lines=False, warning_re=WARNING_RE):
        TestRunner.__init__(self)
        self.warning = warning
        self.warning_re = warning_re
        self.platform = platform
        self.ignore_lines = ignore_lines

    def evaluate(self, build_info, allow_back=False):
        files = retrieve_test_logs(
                build_info.repo_name, build_info.changeset[:12],
                self.platform, warning_re=self.warning_re)

        # Somewhat arbitrary, but we need to make sure there are enough tests
        # run in order to make a reasonable evaluation of the amount of
        # warnings present.
        if len(files) < 10:
            # Tell the bisector to skip this build.
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


        # TODO(ER): Replace arbitrary threshold.
        if total > 1000:
            return 'b'
        else:
            return 'g'

    def run_once(self, build_info):
        return 0 if self.evaluate(build_info) == 'g' else 1


def retrieve_test_logs(repo, revision, platform='linux64',
                       cache_dir=None, use_cache=True,
                       warning_re=WARNING_RE):
    """
    Retrieves and processes the test logs for the given revision.

    Returns list of processed files.
    """
    if not cache_dir:
        cache_dir = "%s-%s-%s" % (repo, revision, platform)

    files = None
    cache_dir_exists = os.path.isdir(cache_dir)
    if cache_dir_exists and use_cache:
        # We already have logs for this revision.
        print "Using cached data"
        try:
            files = read_cached_results(cache_dir, warning_re)
        except:
            print "Cache file for %s not found" % warning_re

    if not files:
        client = TreeherderClient(protocol='https', host='treeherder.mozilla.org')
        result_set = client.get_resultsets(repo, revision=revision)
        if not result_set:
            print "Failed to find %s in %s" % (revision, repo)
            return None

        # We just want linux64 debug builds:
        #   - platform='linux64'
        #   - Crazytown param for debug: option_collection_hash
        for x in range(5):
            try:
                jobs = client.get_jobs(repo,
                                       result_set_id=result_set[0]['id'],
                                       count=5000, # Just make this really large to avoid pagination
                                       platform=platform,
                                       option_collection_hash=DEBUG_OPTIONHASH)
            except requests.exceptions.ConnectionError:
                pass

        if not jobs:
            print "No jobs found for %s %s" % (revision, platform)
            return None

        #platforms = set()
        #for job in jobs:
        #    platforms.add(job['build_platform'])
        #pprint.pprint(platforms)
        #pprint.pprint(jobs[0])
        #return None

        if cache_dir_exists:
            if not use_cache:
                shutil.rmtree(cache_dir)
                os.mkdir(cache_dir)
        else:
            os.mkdir(cache_dir)

        # Bind fixed arguments to the |download_log| call.
        partial_download_log = partial(download_log, dest=cache_dir,
                                      repo=repo, revision=revision,
                                      warning_re=warning_re)

        pool = Pool(processes=24)
        files = pool.map(partial_download_log, jobs)
        pool.close()

        cache_results(cache_dir, files, warning_re)

    return files


def main():
    parser = ArgumentParser()
    add_arguments(parser)
    cmdline = parser.parse_args()

    if cmdline.bisect:
        from mozregression.fetch_configs import create_config
        from mozregression.dates import parse_date
        from mozregression.log import init_logger
        init_logger(debug=True)

        (_os, bits) = re.match(r'([a-zA-Z]+)-?([0-9]+)?', cmdline.platform).groups()
        if not bits:
            bits = 32

        if _os.startswith('win'):
            _os = 'win'

        # TODO(ER): Support revisions as well as dates.
        first_date = parse_date(cmdline.bisect)
        last_date = parse_date(cmdline.revision)

        fetch_config = create_config('firefox', _os, int(bits))
        fetch_config.set_repo(cmdline.repo)
        fetch_config.set_build_type('debug')

	#info_fetcher = InboundInfoFetcher(fetch_config)
	#build_info = info_fetcher.find_build_info(cmdline.revision)
	#last_date = build_info.build_date

        test_runner = WarningTestRunner(
                cmdline.warning, cmdline.platform,
                ignore_lines=cmdline.ignore_lines,
                warning_re=cmdline.warning_re)

        bisector = Bisector(
                fetch_config,
                test_runner,
                None,
                False,
                None)

        handler = NightlyHandler(ensure_good_and_bad=True)
        result = bisector.bisect(handler, first_date, last_date)
        if result == Bisection.FINISHED:
            print "Got as far as we can go bisecting nightlies..."
            handler.print_range()
            print "Switching bisection method to taskcluster"
            fetch_config.set_repo(fetch_config.get_nightly_repo(handler.bad_date))

            good_revision = handler.good_revision
            bad_revision = handler.bad_revision

            def bisect_inbound(good_rev, bad_rev):
                handler = InboundHandler()
                result = bisector.bisect(handler, good_rev, bad_rev, expand=0)
                if result == Bisection.FINISHED:
                    print "Oh noes, no (more) inbound revisions :("
                    handler.print_range()
                    if len(handler.build_range) == 2:
                        result = handler.handle_merge()
                        if result:
                            branch, good_rev, bad_rev = result
                            fetch_config.set_repo(branch)
                            bisect_inbound(good_rev, bad_rev)

            bisect_inbound(good_revision, bad_revision)


        print "Done bisecting I guess"
        return


    files = retrieve_test_logs(cmdline.repo, cmdline.revision, cmdline.platform,
                               cmdline.cache_dir, cmdline.use_cache,
                               cmdline.warning_re)

    combined_warnings = Counter()
    for log in files:
        if log:
            combined_warnings.update(log.warnings)

    if not cmdline.warning:
        print "Top %d Warnings" % cmdline.warning_count
        print "==============="
        if cmdline.reverse:
            warnings_list = combined_warnings.most_common()[:-cmdline.warning_count:-1]
        else:
            warnings_list = combined_warnings.most_common(cmdline.warning_count)

        for (warning, count) in warnings_list:
            print "%6d %s" % (count, warning)

        print "TOTAL WARNINGS: %d" % sum(combined_warnings.values())
    else:
        # Sanity check the warning format.
        if not re.match(cmdline.warning_re, cmdline.warning):
            print "Provided warning %s does not match warning regex %s" % (cmdline.warning, cmdline.warning_re)
            return

        cache_dir = cmdline.cache_dir
        if not cache_dir:
            cache_dir = "%s-%s-%s" % (cmdline.repo, cmdline.revision, cmdline.platform)

        info = WarningInfo(cmdline.warning, combined_warnings[cmdline.warning])
        info.match_in_logs(cache_dir, files)
        (summary, details) = info.details(
                cmdline.repo, cmdline.revision,
                cmdline.platform, cmdline.test_summary_count)

        if cmdline.create_bug:
            if not cmdline.component:
                print "Must specify component."
                return

            if not info.count:
                print "There are zero warnings matching %s" % cmdline.warning
                print "Not filing bug!"
                return

            api_key = cmdline.api_key
            if not api_key:
                try:
                    cfg = ConfigParser.ConfigParser()
                    cfg.read(os.path.join(os.path.expanduser('~'), '.hgrc'))
                    api_key = cfg.get('bugzilla', 'apikey')
                except Exception, e:
                    print "I'm sorry, I couldn't guess your api key. Please " \
                          "specify it with --api_key"
                    print e
                    return

            bz = Bugzilla(BUGZILLA_API, api_key)
            result = bz.create_bug(
                    summary, details, component=cmdline.component,
                    product=cmdline.product)
            print "Filed bug %d" % result['id']
        else:
            print "\n".join([summary, "", details])


if __name__ == '__main__':
    main()
