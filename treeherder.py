#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from multiprocessing import Pool
import pprint
import re

import requests
from thclient import TreeherderClient


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


def download_log(job):
    """
    Downloads the log file for the given job.

    Returns the log file name.
    """
    job_id = job['id']
    job_name = job['job_type_name']

    print "Downloading log for %s %d" % (job_name, job_id)

    client = TreeherderClient(protocol='https', host='treeherder.mozilla.org')
    job_log = client.get_job_log_url('try', job_id=job_id)

    job_log_url = job_log[0]['url']
    job_log_name = job_name.replace(' ', '_') + '.log'

    r = requests.get(job_log_url, stream=True)
    with open(job_log_name, 'w') as f:
        for x in r.iter_lines():
            if x:
                f.write(normalize_line(x) + '\n')

    return job_log_name


def main():
    client = TreeherderClient(protocol='https', host='treeherder.mozilla.org')
    result_set = client.get_resultsets('try', revision='e4d695e4884f2ce1365e8cc3d1ae4402cce4919a')

    # We just want linux64 debug builds:
    #   - platform='linux64'
    #   - Crazytown param for debug: option_collection_hash=32faaecac742100f7753f0c1d0aa0add01b4046b
    jobs = client.get_jobs('try',
                           result_set_id=result_set[0]['id'],
                           count=5000, # Just make this really large to avoid pagination
                           platform='linux64',
                           option_collection_hash='32faaecac742100f7753f0c1d0aa0add01b4046b')
    print "Found %d jobs" % len(jobs)

    pool = Pool(processes=12)
    files = pool.map(download_log, jobs)
    pool.close()



if __name__ == '__main__':
    main()
