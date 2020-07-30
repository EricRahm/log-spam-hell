# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime

from collections import Counter
from functools import partial

from logspam import WARNING_RE
import logspam.cache

import json
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
                    # For structured logs the test start info is contained in a
                    # JSON blob. Try to extract it here and fall back to a
                    # regex if it doesn't work.
                    try:
                        json_line = json.loads(line)
                        if 'action' in json_line and json_line['action'] == \
                        'test_start':
                            curr_test = e10s_prefix + json_line['test']
                        else:
                            line = json_line['data']
                    except:
                        pass

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
                        print("Can't read line:\n  %s" % line)

            if not curr_test:
                print("No test names matched?")
            elif not self.tests:
                print("No warnings matched?")

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

        link = "https://hg.mozilla.org/%s/annotate/%s/%s#l%d" % (
                    BRANCH_MAP.get(repo, repo), revision, self.file, int(self.line))

        details = []
        details.append("## %d %s" % (self.count, self.full_text))
        details.append("")
        details.append("This warning [[1]](%s) shows up in the following test suites:" % link)
        details.append("```")
        for (job, count) in self.jobs.most_common():
            details.append("%6d - %s" % (count, job))
        details.append("```")
        details.append("It shows up in %d tests. A few of the most prevalent:" % len(self.tests))
        details.append("```")
        for (test, count) in self.tests.most_common(test_count):
            details.append("%6d - %s" % (count, test))
        details.append("```")
        details.append("[1] %s" % link)

        return (summary, "\n".join(details), self.file)

def download_log(job, dest, repo, revision, warning_re):
    """
    Downloads the log file for the given job.

    Returns the log file name.
    """
    job_id = job['id']
    job_name = job['job_type_name']
    if job['job_type_symbol']:
        job_name += " " + job['job_type_symbol'] # Needed for jobs without unique names

    print("Downloading log for %s %d" % (job_name, job_id))

    try:
        # TODO(ER): We could cleanup log name handling.
        job_log_url = job['url']

        # For some jobs errorssummary.log is now the default, but that doesn't
        # include gecko warnings. Switch over to the raw log.
        if 'errorsummary.log' in job_log_url:
            job_log_url = re.sub('errorsummary', 'raw', job_log_url)

        print("job_log_url = %s" % job_log_url)

    except:
        print("Couldn't determine job log URL for %s" % job_name)
        return None

    parsed_log = logspam.cache.ParsedLog(url=job_log_url, job_name=job_name)
    if not parsed_log.download(dest, warning_re):
        print("Couldn't download log URL for %s" % job_name)
        return None

    return parsed_log


def add_log_urls_to_jobs(jobs, job_urls):
    """
    Helper that maps the results of a job_log_url query to the actual job
    objects. It's possilbe for a job to have multiple logs, for now we
    just choose the first one.
    """
    id_to_log = {}
    for job_log in job_urls:
        job_id = job_log['job_id']

        # Only take the first log found for each job.
        # Another option is to check the log name. For taskcluster builds at
        # least this seems to be job_log['name'] == 'builds-4h'.
        if not job_id in id_to_log:
            id_to_log[job_id] = job_log['url']

    # Now add the URL to the job object.
    for job in jobs:
        job_id = job['id']
        if job_id in id_to_log:
            job['url'] = id_to_log[job['id']]
        else:
            print("Missing job? %d" % job_id)


def get_latest_revision(repo):
    """
    Gets the latest revision pushed to the given repo.
    """
    client = TreeherderClient()
    push_log = client.get_pushes(repo)

    EPOCH = datetime.datetime(1970,1,1)
    NOW_TS = (datetime.datetime.utcnow() - EPOCH).total_seconds()

    # We need a push old enough that it probably is done testing
    MIN_ELAPSED = datetime.timedelta(hours=3).total_seconds()
    for push in push_log:
        if NOW_TS - push['push_timestamp'] > MIN_ELAPSED:
            print("revision %s is old enough" % push['revision'])
            return push['revision']

    return


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
        print("Using cached data")
        try:
            return cache.read_results()
        except logspam.cache.CacheFileNotFoundException as e:
            print("Cache file for %s not found" % warning_re)
            print(e)

    client = TreeherderClient()
    print("getting result set")
    pushes = client.get_pushes(repo, revision=revision)
    print("pushes = client.get_pushes('%s', revision='%s')" % (repo, revision))
    print("got pushes")
    if not pushes:
        print("Failed to find %s in %s" % (revision, repo))
        return None

    print("getting jobs")
    for x in range(5):
        try:
            # option_collection_hash is just the convoluted way of specifying
            # we want a debug build.
            print("jobs = client.get_jobs('%s',result_set_id=%d, count=5000, platform='%s', option_collection_hash='%s')" % (
                    repo, pushes[0]['id'], platform, DEBUG_OPTIONHASH))
            jobs = client.get_jobs(repo,
                                   result_set_id=pushes[0]['id'],
                                   count=5000, # Just make this really large to avoid pagination
                                   platform=platform,
                                   option_collection_hash=DEBUG_OPTIONHASH,
                                   state='completed')
            break
        except requests.exceptions.ConnectionError:
            pass

    if not jobs:
        print("No jobs found for %s %s" % (revision, platform))
        import traceback
        traceback.print_exc()
        return None

    print("got jobs")

    print("getting %d job log urls" % len(jobs))
    job_ids = [ job['id'] for job in jobs ]
    print(job_ids)
    for x in range(5):
        logs = []
        try:
            for y in range(0, len(job_ids), 100):
                logs = logs + client.get_job_log_url(repo, job_id=job_ids[y:y+100])
            job_logs = logs
            break
        except requests.exceptions.ConnectionError as e:
            pass

    if not job_logs:
        print("Unable to retrieve log urls for %s %s" % (revision, platform))
        import traceback
        traceback.print_exc()
        return None

    add_log_urls_to_jobs(jobs, job_logs)

    print("got job log urls")
    print("%s" % jobs)

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
