#!/usr/bin/env python3

# ***** BEGIN GPL LICENSE BLOCK *****
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
# ***** END GPL LICENCE BLOCK *****

"""
Test packing a directory of blend files.

eg:
    bam_pack_test.py /path/to/blend_files
"""

# ------------------
# Ensure module path
import os
import sys
path = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "client", "cli"))
if path not in sys.path:
    sys.path.append(path)
del os, sys, path
# --------

import os
import sys



def iter_files(path, filename_check=None):
    for dirpath, dirnames, filenames in sorted(os.walk(path)):

        # skip '.svn'
        if dirpath.startswith(".") and dirpath != ".":
            continue

        for filename in sorted(filenames):
            filepath = os.path.join(dirpath, filename)
            if filename_check is None or filename_check(filepath):
                yield filepath


def iter_blends(path):
    yield from iter_files(path, filename_check=lambda f: os.path.splitext(f)[1].lower() == ".blend")


def pack_blend_test(blendfile):
    TEMP_ZIP = "temp.zip"
    argv = (
        "pack", blendfile,
        "--output", TEMP_ZIP,
        "--quiet",
        )

    import bam
    print("bam", " ".join(argv))
    bam.main(argv)


def pack_blend_recursive_test(
        paths,
        blender_bin="blender",
        ):
    for path in paths:
        for f in iter_blends(path):
            pack_blend_test(f)


def create_argparse():
    import os
    import argparse

    usage_text = (
        "Run this script to extract blend-files(s) to a destination path:" +
        os.path.basename(__file__) +
        "--input=FILE --output=FILE [options]")

    parser = argparse.ArgumentParser(description=usage_text)

    # for main_render() only, but validate args.
    parser.add_argument(
            dest="paths", nargs="*",
            help="Path(s) to operate on",
            )
    parser.add_argument(
            "-b", "--blender", dest="blender_bin", metavar='PROGRAM',
            help="The Blender binary used for validation",
            )

    return parser


def main(argv=None):

    if argv is None:
        argv = sys.argv[1:]

    parser = create_argparse()
    args = parser.parse_args(argv)

    pack_blend_recursive_test(
            args.paths,
            blender_bin=args.blender_bin or "blender",
            )


if __name__ == "__main__":
    main()

