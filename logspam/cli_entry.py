#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Script used as a CLI entry point.
"""

from argparse import ArgumentParser

from logspam.bisect import BisectCommandLineArgs
from logspam.bugzilla import FileCommandLineArgs
from logspam.report import ReportCommandLineArgs

def add_arguments(p):
    """
    Adds command-line arguments to the given argparser.
    """
    subparsers = p.add_subparsers(
            title='subcommands',
            description='Commands supported by the logspam tool')

    for command in (ReportCommandLineArgs, FileCommandLineArgs,
                    BisectCommandLineArgs):
        args = command()
        args.add_command(subparsers)

    return

def main():
    parser = ArgumentParser()
    add_arguments(parser)
    cmdline = parser.parse_args()
    cmdline.func(cmdline)
    return

if __name__ == '__main__':
    main()
