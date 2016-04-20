#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from multiprocessing import Pool
import pprint

import requests
from thclient import TreeherderClient


def download_log(job):
    """
    Downloads the log file for the given job.

    Returns the log file name.
    """
    job_id = job['id']
    job_name = job['job_type_name']

    print "Downloading log for %s" % job_name

    client = TreeherderClient(protocol='https', host='treeherder.mozilla.org')
    job_log = client.get_job_log_url('mozilla-central', job_id=job_id)
    job_log_url = job_log[0]['url']
    job_log_name = job_name.replace(' ', '_') + '.log'
    r = requests.get(job_log_url, stream=True)
    with open(job_log_name, 'wb') as f:
        for x in r.iter_content(4096):
            if x:
                f.write(x)

    return job_log_name


def main():
    client = TreeherderClient(protocol='https', host='treeherder.mozilla.org')
    result_set = client.get_resultsets('mozilla-central', revision='ae7413abfa4d3954a6a4ce7c1613a7100f367f9a')
    pprint.pprint(result_set)

    jobs = client.get_jobs('mozilla-central', result_set_id=result_set[0]['id'], count=5000)
    print "Found %d jobs" % len(jobs)
    jobs = [ job for job in jobs if job['platform_option'] == 'debug' and job['platform'] == 'linux64' ]

    print "Filtered to %d logs" % len(jobs)

    pool = Pool(processes=8)
    files = pool.map(download_log, jobs)
    pool.close()



if __name__ == '__main__':
    main()
