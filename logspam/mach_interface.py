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
    Create and returns the logspam ArgumentParser instance.
    """
    p = ArgumentParser()

    if not subcommand:
        subparsers = p.add_subparsers(title='subcommands',
                                      description='valid subcommands',
                                      help='additional help')

        for command in (ReportCommandLineArgs, FileCommandLineArgs, BisectCommandLineArgs):
            args = command()
            args.add_command(subparsers)
    else:
        ARG_HANDLERS = {
            "report": ReportCommandLineArgs,
            "file": FileCommandLineArgs,
            "bisect": BisectCommandLineArgs,
        }

        ARG_HANDLERS[subcommand]().add_arguments(p)

    return p


def run(options):
    """
    Run logspam given a dict of options.
    """
    options['func'](options)
