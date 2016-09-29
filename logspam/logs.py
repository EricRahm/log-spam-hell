# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from collections import Counter
from functools import partial

import logspam.cache

from multiprocessing import Pool
import os
import re
import requests
import shutil
from thclient import TreeherderClient

# Mapping of repo names to their path.
BRANCH_MAP = {
    'autoland': 'integration/autoland',
    'b2g-inbound': 'integration/b2g-inbound',
    'fx-team': 'integration/fx-team',
    'mozilla-inbound': 'integration/mozilla-inbound'
}

# Magic number for retrieving debug build info from Treeherder
DEBUG_OPTIONHASH = '32faaecac742100f7753f0c1d0aa0add01b4046b'

WARNING_RE='^WARNING'

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

    try:
        job_log_url = job['url']
    except:
        print "Couldn't determine job log URL for %s" % job_name
        return None

    parsed_log = logspam.cache.ParsedLog(url=job_log_url, job_name=job_name)
    if not parsed_log.download(dest, warning_re):
        print "Couldn't download log URL for %s" % job_name
        return None

    return parsed_log

def retrieve_test_logs(repo, revision, platform='linux64',
                       cache_dir=None, use_cache=True,
                       warning_re=WARNING_RE):
    """
    Retrieves and processes the test logs for the given revision.

    Returns list of processed files.
    """
    if not cache_dir:
        cache_dir = "%s-%s-%s" % (repo, revision, platform)

    cache = logspam.cache.Cache(cache_dir, warning_re)

    cache_dir_exists = os.path.isdir(cache_dir)
    if cache_dir_exists and use_cache:
        # We already have logs for this revision.
        print "Using cached data"
        try:
            return cache.read_results()
        except logspam.cache.CacheFileNotFoundException as e:
            print "Cache file for %s not found" % warning_re
            print e

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
            break
        except requests.exceptions.ConnectionError:
            pass

    if not jobs:
        print "No jobs found for %s %s" % (revision, platform)
        return None

    # For now we need to determine the log urls one at a time to avoid
    # angering the treeherder gods.
    for job in jobs:
        for x in range(5):
            try:
                job_log = client.get_job_log_url(repo, job_id=job['id'])
                job['url'] = job_log[0]['url']
                break
            except requests.exceptions.ConnectionError:
                pass

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

    cache.store_results(files)

    return files
