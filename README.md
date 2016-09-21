# log-spam-hell
Tools for identifying sources of log spam in mozilla build logs

## Setup
```
pip install git+https:///github.com/EricRahm/log-spam-hell.git
```

## High level usage:
- Go to treeherder: https://treeherder.mozilla.org/#/jobs?repo=mozilla-central
- Choose a *debug* build for the day that's completed, and all tests for the given platform you care about have completed
- Copy the revision hash
- Run:
`log_spam fc15477ce628`
- Choose a warning to get more details on:
`log_spam fc15477ce628 'WARNING: Found channel with no loadinfo, assuming third-party request: file dom/base/ThirdPartyUtil.cpp, line 235'`

By default `mozilla-central` is used and the platform is `linux64`.

Other repos such as `mozilla-inbound` or `try` can be substituted using the `--repo` param. Other platforms such as `windowsxp` can be specified as well using the `--platform` param.

## Bisection
To bisect a warning you can use the `--bisect` flag. It's possible this will just bisect to a change that move the line the warning was on. To deal with that you can use `--ignore-lines`, but only use this if the warning is particularly unique.

*Note: Bisection is pretty flaky and might give you false positives. Double-check the pushlog URL it spits out to see if it's possible there are multiple bugs in the bisected range.*

Example:
```
# Format is: log_spam [--ignore-lines] --bisect <known_good_date> <known_bad_date> <WARNING>
log_spam --ignore-lines --bisect 2016-09-01 2016-09-21 \
    'WARNING: Found channel with no loadinfo, assuming third-party request: file dom/base/ThirdPartyUtil.cpp, line 235'
```

## Filing a bug:

There is basic support for filing a bug containing the output of running `log_spam <hash> <WARNING>` and set as blocking the `logspam` meta bug. By default the bugzilla api key found in your `.hgrc` is used. This can be overridden with `--api-key`.

Example:
```
# Format is: log_spam --create-bug --component <bug_component> [--prodcut <bug_product>] <hash> <WARNING>
log_spam --create-bug --component DOM fc15477ce628 \
    'WARNING: Found channel with no loadinfo, assuming third-party request: file dom/base/ThirdPartyUtil.cpp, line 235'
```

## Full help:
```
usage: log_spam [-h] [--repo REPO] [--no-cache] [--cache-dir CACHE_DIR]
                [--warning-count WARNING_COUNT]
                [--test-summary-count TEST_SUMMARY_COUNT]
                [--platform PLATFORM] [--reverse] [--create-bug]
                [--component COMPONENT] [--product PRODUCT]
                [--api-key API_KEY] [--warning-re WARNING_RE]
                [--bisect BISECT] [--ignore-lines]
                revision [warning]

positional arguments:
  revision              Revision to retrieve logs for.
  warning               Optional: The text of a warning you want the full
                        details of.

optional arguments:
  -h, --help            show this help message and exit
  --repo REPO           Repository the revision corresponds to. Default:
                        mozilla-central
  --no-cache            Redownload logs if already present.
  --cache-dir CACHE_DIR
                        Directory to cache logs to. Default: <repo>-<revision>
  --warning-count WARNING_COUNT
                        Number of warnings to show in the default summary.
                        Default: 40
  --test-summary-count TEST_SUMMARY_COUNT
                        Number of tests to list in warning summary mode.
                        Default: 10
  --platform PLATFORM   Platform to get logs for. Default: linux64
  --reverse             Print the least common warnings instead.
  --create-bug          Create a new bug for the specified warning.
  --component COMPONENT
                        Component to file the bug in.
  --product PRODUCT     Product to file the bug in. Default: Core
  --api-key API_KEY     The API key to use when creating the bug. Default:
                        extracted from .hgrc
  --warning-re WARNING_RE
                        Regex used to match lines. Can be used to match debug
                        messages that are not proper warnings.
  --bisect BISECT       Date to bisect from.
  --ignore-lines        Ignore line numbers when bisecting warnings. Useful if
                        the line number of the warning has changed. Not so
                        useful if there are a lot of similar warnings in the
                        file.
```
