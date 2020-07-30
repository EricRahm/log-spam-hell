# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from collections import Counter
import hashlib
import io
import json
import os
import re
import requests

from logspam import WARNING_RE

class CacheFileNotFoundException(Exception):
    pass

def normalize_line(line):
    """
    Normalizes the given line to make comparisons easier. Removes:
      - timestamps
      - pids
      - trims file paths
      - stuff that looks like a pointer address
    """
    line = line.decode('utf-8')
    try:
        # Raw logs are now encoded in json
        json_line = json.loads(line)
        line = json_line['data']
    except:
        # Legacy logs may be plain text, particularly if live_backing.log is
        # specified.
        pass

    # taskcluster prefixing:
    #   [task 2016-09-20T11:09:35.539828Z] 11:09:35
    line = re.sub(r'^\[task[^\]]+\]\s', '', line)
    line = re.sub(r'^[0-9:]+\s+INFO\s+-\s+', '', line)
    line = re.sub(r'^[0-9]+\s+INFO\s+', '', line)
    line = re.sub(r'^PROCESS \| [0-9]+ \| ', '', line)
    #PID 13497 |  WARNING:
    line = re.sub(r'^PID\s+[0-9]+\s+\|\s+', '', line)
    line = re.sub(r'\[(Child|Parent|GMP|NPAPI)?\s?[0-9]+\]', '', line)
    line = re.sub(r'/home/worker/workspace/build/src/', '', line)
    line = re.sub(r'/builds/worker/checkouts/gecko/', '', line)
    # Attempt buildbot paths, ie:
    #  c:/builds/moz2_slave/m-cen-w32-d-000000000000000000/build/src/
    line = re.sub(r'([a-z]:)?/builds/[^/]+/[^/]+/build/src/', '', line)
    #  z:/build/build/src/
    line = re.sub(r'([a-z]:)?/(build/)+src/', '', line)
    #blah=1caa2c00
    line = re.sub(r'=[a-z0-9]+', '=NNNNNN', line)
    #GECKO(1265) |
    line = re.sub(r'GECKO\([0-9]+\) \|', '', line)
    line = line.strip()
    #[1355, Main Thread]
    line = re.sub(r'^\[[^\]]+\]\s+', '', line)

    return line

class CustomEncoder(json.JSONEncoder):
    """
    Custom JSON encoder that handles ParsedLog objects.
    """
    def default(self, obj):
        if isinstance(obj, ParsedLog):
            return obj.to_json()
        return json.JSONEncoder.default(self, obj)

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
            # Use |io.open| to handle unicode weirdness
            with io.open(dest, 'r', encoding='utf-8') as f:
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

def cache_file_path(cache_dir, warning_re):
    """
    Generates the cache file name.
    """
    if warning_re != WARNING_RE:
        warning_md5 = hashlib.md5(warning_re).hexdigest()
        return os.path.join(cache_dir, "results.%s.json" % warning_md5)
    else:
        return os.path.join(cache_dir, "results.json")


class Cache(object):
    def __init__(self, cache_dir, warning_re):
        self.path = cache_file_path(cache_dir, warning_re)

    def store_results(self, parsed_logs):
        """
        Caches the parsed results in a json file.
        """
        with open(self.path, 'w') as f:
            json.dump(parsed_logs, f, cls=CustomEncoder)

    def read_results(self):
        """
        Reads the cached results from a previous run.
        """
        if not os.path.isfile(self.path):
            raise CacheFileNotFoundException(
                    "Cache file %s not found" % self.path)

        print(("Reading cache from %s" % self.path))
        parsed_logs = []
        with open(self.path, 'r') as f:
            try:
                raw_list = json.load(f)
            except Exception:
                # Corrupt json file, nuke it.
                os.remove(self.path)
                raise CacheFileNotFoundException(
                        "Cache file %s was corrupt", self.path)

            for x in raw_list:
                if not x:
                    continue
                log = ParsedLog(x['url'], x['job_name'], x['fname'])
                log.warnings.update(x['warnings'])
                parsed_logs.append(log)

        return parsed_logs
