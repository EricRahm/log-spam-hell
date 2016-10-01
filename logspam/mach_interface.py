# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


"""
This module provides an API to integrate logspam within mach.

Be careful to not break backward compatibility here, or you will
break mach!
"""

from argparse import (ArgumentParser, Namespace)

from logspam import __version__

from logspam.bisect import BisectCommandLineArgs
from logspam.bugzilla import FileCommandLineArgs
from logspam.report import ReportCommandLineArgs

import requests

ARG_HANDLERS = {
    'report': ReportCommandLineArgs,
    'file': FileCommandLineArgs,
    'bisect': BisectCommandLineArgs,
}

RUN_HANDLERS = {
    'report': ReportCommandLineArgs.do_report,
    'file': FileCommandLineArgs.do_file,
    'bisect': BisectCommandLineArgs.do_bisect,
}

def new_release_on_pypi():
    """
    Check if a new release is available on pypi and returns it.

    None is returned in case of error or if there is no new version.
    """
    try:
        url = "https://pypi.python.org/pypi/mozilla-log-spam/json"
        pypi_version = requests.get(url, timeout=10).json()['info']['version']
    except Exception:
        return
    if pypi_version != __version__:
        return pypi_version


def parser(subcommand=None):
    """
    Create and returns the logspam ArgumentParser instance. Mach doesn't seem to
    be able to handle an ArgumentParser with subcommands properly so we support
    just returning the parser for a given subcommand.

    :param subcommand: Should be one of 'report', 'file', or 'bisect'.
    """
    p = ArgumentParser()

    if not subcommand:
        subparsers = p.add_subparsers(title='subcommands',
                                      description='valid subcommands',
                                      help='additional help')

        for (_, command) in ARG_HANDLERS.iteritems():
            args = command()
            args.add_command(subparsers)
    else:
        ARG_HANDLERS[subcommand]().add_arguments(p)

    return p


class FakeArgumentParser(object):
    """
    Mach gives us a dictionary of params instead of an argparse named-tuple type
    instance. Here we emulate what argparse would give us where you can do
    `foo.bar` rather than `foo[bar]`.
    """
    def __init__(self, entries):
        self.__dict__.update(entries)


def run(options):
    """
    Run logspam given a dict of options.
    """
    # Mach doesn't propagate the `func` param for some reason, so we have to do
    # a manual mapping.
    RUN_HANDLERS[options['command']](FakeArgumentParser(options))

def test():
    """
    Ad-hoc test for mach_interface.
    """
    options = {'cache_dir': None,
         'platform': 'linux64',
         'repo': 'mozilla-central',
         'reverse': False,
         'revision': '5ffed033557e',
         'test_summary_count': 10,
         'use_cache': True,
         'warning': None,
         'warning_count': 40,
         'warning_re': '^WARNING',
         'command': 'report'}
    run(options)
