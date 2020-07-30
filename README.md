# log-spam-hell
Tools for identifying sources of log spam in mozilla build logs

## Setup
```
pip install git+https:///github.com/EricRahm/log-spam-hell.git
```

## Basic usage:
To just get a report for the latest changeset that has a reasonable number of test results:
`log_spam report latest`

## High level usage:
- Go to treeherder: https://treeherder.mozilla.org/#/jobs?repo=mozilla-central
- Choose a *debug* build for the day that's completed, and all tests for the given platform you care about have completed
- Copy the revision hash
- Run:
`log_spam report fc15477ce628`
- Choose a warning to get more details on:
`log_spam report fc15477ce628 'WARNING: Found channel with no loadinfo, assuming third-party request: file dom/base/ThirdPartyUtil.cpp, line 235'`

By default `mozilla-central` is used and the platform is `linux1804-64`.

Other repos such as `autoland` or `try` can be substituted using the `--repo` param. Other platforms such as `windows10-64` can be specified as well using the `--platform` param.

## Bisection
To bisect a warning you can use the `bisect` sub-command. It's possible this will just bisect to a change that move the line the warning was on. To deal with that you can use `--ignore-lines`, but only use this if the warning is particularly unique.

*Note: Bisection is pretty flaky and might give you false positives. Double-check the pushlog URL it spits out to see if it's possible there are multiple bugs in the bisected range.*

Example:
```
# Format is: log_spam bisect [--ignore-lines] <known_good_date> <known_bad_date> <WARNING>
log_spam bisect --ignore-lines 2016-09-01 2016-09-21 \
    'WARNING: Found channel with no loadinfo, assuming third-party request: file dom/base/ThirdPartyUtil.cpp, line 235'
```

## Filing a bug:

There is basic support for filing a bug containing the output of running `log_spam report <hash> <WARNING>` and set as blocking the `logspam` meta bug. By default the bugzilla api key found in your `.hgrc` is used. This can be overridden with `--api-key`.

Example:
```
# Format is: log_spam file --component <bug_component> [--prodcut <bug_product>] <hash> <WARNING>
log_spam --create-bug --component DOM fc15477ce628 \
    'WARNING: Found channel with no loadinfo, assuming third-party request: file dom/base/ThirdPartyUtil.cpp, line 235'

# If you have a local checkout we can figure out the component
log_spam --hgroot ~/mozilla-unified fc15477ce628 \
    'WARNING: Found channel with no loadinfo, assuming third-party request: file dom/base/ThirdPartyUtil.cpp, line 235'
```

## Full help:
### Top-level
```
usage: log_spam [-h] {report,file,bisect} ...

optional arguments:
  -h, --help            show this help message and exit

subcommands:
  Commands supported by the logspam tool

  {report,file,bisect}
    report              Generates an overall warning report or a report for a specific warning.
    file                Files a logspam bug in bugzilla for the given warning.
    bisect              Attempts to find the changeset that introduced a given warning through bisection.
```
### Report
```
usage: log_spam report [-h] [--platform PLATFORM] [--warning-re WARNING_RE] [--repo REPO] [--no-cache]
                       [--cache-dir CACHE_DIR] [--warning-count WARNING_COUNT]
                       [--test-summary-count TEST_SUMMARY_COUNT] [--reverse]
                       revision [warning]

positional arguments:
  revision              Revision to retrieve logs for.
  warning               Optional: The text of a warning you want the full details of.

optional arguments:
  -h, --help            show this help message and exit
  --platform PLATFORM   Platform to get logs for. Default: linux1804-64
  --warning-re WARNING_RE
                        Regex used to match lines. Can be used to match debug messages that are not proper warnings.
  --repo REPO           Repository the revision corresponds to. Default: mozilla-central
  --no-cache            Redownload logs if already present.
  --cache-dir CACHE_DIR
                        Directory to cache logs to. Default: <repo>-<revision>
  --warning-count WARNING_COUNT
                        Number of warnings to show in the default summary. Default: 40
  --test-summary-count TEST_SUMMARY_COUNT
                        Number of tests to list in warning summary mode. Default: 10
  --reverse             Print the least common warnings instead.
```
### File
```
usage: log_spam file [-h] [--platform PLATFORM] [--warning-re WARNING_RE] [--repo REPO] [--no-cache]
                     [--cache-dir CACHE_DIR] [--warning-count WARNING_COUNT]
                     [--test-summary-count TEST_SUMMARY_COUNT] [--reverse]
                     (--component COMPONENT | --hgroot HGROOT) [--product PRODUCT]
                     [--api-key API_KEY]
                     revision warning

positional arguments:
  revision              Revision to retrieve logs for.
  warning               The text of a warning you want the full details of.

optional arguments:
  -h, --help            show this help message and exit
  --platform PLATFORM   Platform to get logs for. Default: linux1804-64
  --warning-re WARNING_RE
                        Regex used to match lines. Can be used to match debug messages that are not proper warnings.
  --repo REPO           Repository the revision corresponds to. Default: mozilla-central
  --no-cache            Redownload logs if already present.
  --cache-dir CACHE_DIR
                        Directory to cache logs to. Default: <repo>-<revision>
  --warning-count WARNING_COUNT
                        Number of warnings to show in the default summary. Default: 40
  --test-summary-count TEST_SUMMARY_COUNT
                        Number of tests to list in warning summary mode. Default: 10
  --reverse             Print the least common warnings instead.
  --component COMPONENT
                        Component to file the bug in.
  --hgroot HGROOT       local mozilla repo to use for mapping components
  --product PRODUCT     Product to file the bug in. Default: Core
  --api-key API_KEY     The API key to use when creating the bug. Default: extracted from .hgrc
```
### Bisect
```
usage: log_spam bisect [-h] [--platform PLATFORM] [--warning-re WARNING_RE] [--ignore-lines]
                       [--warning-limit WARNING_LIMIT] [--required-test REQUIRED_TEST]
                       good bad warning

positional arguments:
  good                  Last known good date. Will be validated.
  bad                   Last known bad date.
  warning               The text of a warning you want the full details of.

optional arguments:
  -h, --help            show this help message and exit
  --platform PLATFORM   Platform to get logs for. Default: linux1804-64
  --warning-re WARNING_RE
                        Regex used to match lines. Can be used to match debug messages that are not proper warnings.
  --ignore-lines        Ignore line numbers when bisecting warnings. Useful if the line number of the warning has changed. Not so useful if there are a lot of similar warnings in the file.
  --warning-limit WARNING_LIMIT
                        The threshold of warnings for going from good to bad. Default: 1000.
  --required-test REQUIRED_TEST
                        Test that must be present to compare revisions
```

## Developers

### Configuration
I highly suggest working in a virtualenv, manage that however you prefer. We now use Python3.


To setup for development:
```
git clone https://github.com/EricRahm/log-spam-hell.git
cd log-spam-hell
virtualenv venv
source venv/bin/activate
pip3 install -e .
```
### Common issues
- *Normalizing paths* The paths in warnings are actually absolute paths. We normalize them so they're relative to a normal source checkout. This often breaks when releng changes build machine configurations so you'll have to update the [normalize_line function](logspam/cache.py).
- *Platform names* We occosionally change the name of a platform, if you see very few results go over to treeherder, select the test you're interested in, and check out what the platform name is in the job description.
- *Log format* The default log that gets returned and the format it is in can change as well. You can look at the log artifact in treeherder to get an idea of what's changed.

