#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from argparse import ArgumentParser
from collections import Counter
from functools import partial
import json
from multiprocessing import Pool
import os
import pprint
import re
import shutil

import requests
from thclient import TreeherderClient

DEBUG_OPTIONHASH = '32faaecac742100f7753f0c1d0aa0add01b4046b'

def normalize_line(line):
    """
    Normalizes the given line to make comparisons easier. Removes:
      - timestamps
      - pids
      - trims file paths
    """
    line = re.sub(r'^[0-9:]+\s+INFO\s+-\s+', '', line)
    line = re.sub(r'^PROCESS \| [0-9]+ \| ', '', line)
    line = re.sub(r'\[(Child|Parent|GMP|NPAPI)?\s?[0-9]+\]', '[NNNNN]', line)
    line = re.sub(r'/home/worker/workspace/build/src/', '', line)

    return line


class ParsedLog:
    """
    Represents a log file that was downloaded and processed.
    """
    def __init__(self, url, fname):
        self.url = url
        self.fname = fname
        self.warnings = Counter()

    def download(self):
        """
        Downloads the log file and normalizes it. Warnings are also
        accumulated.
        """
        r = requests.get(self.url, stream=True)
        with open(self.fname, 'w') as f:
            for x in r.iter_lines():
                if x:
                    line = normalize_line(x)
                    self.add_warning(line)
                    f.write(line + '\n')

    def add_warning(self, line):
        """
        Adds the line to the set of warnings if it contains a warning.
        """
        if 'WARNING' in line:
            self.warnings[line] += 1

    def to_json(self):
        """
        Creates a json representation of this object.
        """
        return {
            'url': self.url,
            'fname': self.fname,
            'warnings': dict(self.warnings)
        }


def download_log(job, dest, repo, revision):
    """
    Downloads the log file for the given job.

    Returns the log file name.
    """
    job_id = job['id']
    job_name = job['job_type_name']

    print "Downloading log for %s %d" % (job_name, job_id)

    client = TreeherderClient(protocol='https', host='treeherder.mozilla.org')
    job_log = client.get_job_log_url(repo, job_id=job_id)

    parsed_log = ParsedLog(
            url=job_log[0]['url'],
            fname=os.path.join(dest, job_name.replace(' ', '_') + '.log'))

    parsed_log.download()
    return parsed_log


class CustomEncoder(json.JSONEncoder):
    """
    Custom JSON encoder that handles ParsedLog objects.
    """
    def default(self, obj):
        if isinstance(obj, ParsedLog):
            return obj.to_json()
        return json.JSONEncoder.default(self, obj)


def cache_results(dest, parsed_logs):
    """
    Caches the parsed results in a json file.
    """
    fname = os.path.join(dest, "results.json")
    with open(fname, 'w') as f:
        json.dump(parsed_logs, f, cls=CustomEncoder)


def read_cached_results(cache_dir):
    """
    Reads the cached results from a previous run.
    """
    fname = os.path.join(cache_dir, "results.json")
    parsed_logs = []
    with open(fname, 'r') as f:
        raw_list = json.load(f)
        for x in raw_list:
            log = ParsedLog(x['url'], x['fname'])
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
    p.add_argument('--no-cache', action='store_false', default=True, dest='use_cache',
                   help='Redownload logs if already present.')
    p.add_argument('--cache-dir', action='store', default=None,
                   help='Directory to cache logs to. Default: <repo>-<revision>')


def main():
    parser = ArgumentParser()
    add_arguments(parser)
    cmdline = parser.parse_args()

    cache_dir = cmdline.cache_dir
    if not cache_dir:
        cache_dir = "%s-%s" % (cmdline.repo, cmdline.revision)

    cache_dir_exists = os.path.isdir(cache_dir)
    if cache_dir_exists and cmdline.use_cache:
        # We already have logs for this revision.
        print "Using cached data"
        files = read_cached_results(cache_dir)
    else:
        client = TreeherderClient(protocol='https', host='treeherder.mozilla.org')
        result_set = client.get_resultsets(cmdline.repo, revision=cmdline.revision)

        # We just want linux64 debug builds:
        #   - platform='linux64'
        #   - Crazytown param for debug: option_collection_hash
        jobs = client.get_jobs(cmdline.repo,
                               result_set_id=result_set[0]['id'],
                               count=5000, # Just make this really large to avoid pagination
                               platform='linux64',
                               option_collection_hash=DEBUG_OPTIONHASH)
        print "Found %d jobs" % len(jobs)
        if cache_dir_exists:
            shutil.rmtree(cache_dir)
        os.mkdir(cache_dir)

        # Bind fixed arguments to the |download_log| call.
        partial_download_log = partial(download_log, dest=cache_dir,
                                      repo=cmdline.repo, revision=cmdline.revision)

        pool = Pool(processes=12)
        files = pool.map(partial_download_log, jobs)
        pool.close()

        cache_results(cache_dir, files)

    combined_warnings = Counter()
    for log in files:
        combined_warnings.update(log.warnings)

    print "Top 40 Warnings"
    print "==============="
    for (warning, count) in combined_warnings.most_common(40):
        print "%6d %s" % (count, warning)

    print "TOTAL WARNINGS: %d" % sum(combined_warnings.values())


if __name__ == '__main__':
    main()
