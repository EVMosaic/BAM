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

VERBOSE = 0
BLENDER_EXIT_CODE = 3

# --------------------
# Runs inside Blender!
#
# Cheap hack to avoid having 2x scripts!
import sys
bpy = sys.modules.get("bpy")
if bpy is not None:
    import os

    # ----
    # write paths

    argv = sys.argv
    argv = argv[argv.index("--") + 1:]
    FILE_OUT = argv[0]

    data = bpy.utils.blend_paths(absolute=True)
    data = [(f, os.path.exists(f)) for f in data]

    import json
    with open(FILE_OUT, 'w', encoding='utf-8') as f:
        json.dump(
                data, f, ensure_ascii=False,
                check_circular=False,
                # optional (pretty)
                sort_keys=True, indent=4, separators=(',', ': '),
                )
    sys.exit(BLENDER_EXIT_CODE)


del bpy

# End Blender Code!
# -----------------


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



def args_as_string(args):
    """ Print args so we can paste them to run them again.
    """
    import shlex
    return " ".join([shlex.quote(c) for c in args])


def run(cmd, cwd=None):
    if VERBOSE:
        print(">>> ", args_as_string(cmd))
    import subprocess
    kwargs = {
        "stderr": subprocess.PIPE,
        "stdout": subprocess.PIPE,
        }
    if cwd is not None:
        kwargs["cwd"] = cwd

    proc = subprocess.Popen(cmd, **kwargs)
    stdout, stderr = proc.communicate()
    returncode = proc.returncode

    if VERBOSE:
        sys.stdout.write("   stdout:  %s\n" % stdout.strip())
        sys.stdout.write("   stderr:  %s\n" % stderr.strip())
        sys.stdout.write("   return:  %d\n" % returncode)

    return stdout, stderr, returncode


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


def pack_blend_test(blendfile_src, log, blender_bin):

    def json_from_file(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            import json
            return json.load(f)

    def args_blender_read_paths(filepath):
        return (
            blender_bin,
            "--background",
            filepath,
            "-noaudio",
            "--python", __file__,
            "--",
            FILE_OUT,
            )

    def unzip(filepath_src, path_dst):
        import zipfile
        with zipfile.ZipFile(filepath_src) as zf:
            zf.extractall(path_dst)


    import shutil
    TEMP_ZIP = "/tmp/temp.zip"
    TEMP_EXTRACT = "/tmp/temp_out"
    FILE_OUT = "/tmp/files.json"

    def cleanup():
        _ = TEMP_EXTRACT
        if os.path.exists(_):
            shutil.rmtree(_)
        _ = TEMP_ZIP
        if os.path.exists(_):
            os.remove(_)
        _ = FILE_OUT
        if os.path.exists(_):
            os.remove(_)

    argv = (
        "pack", blendfile_src,
        "--output", TEMP_ZIP,
        "--quiet",
        )

    import bam
    log.info("bam " + " ".join(argv))
    bam.main(argv)

    # extract zip
    os.makedirs(TEMP_EXTRACT, exist_ok=True)
    unzip(TEMP_ZIP, TEMP_EXTRACT)
    os.remove(TEMP_ZIP)

    blendfile_dst = os.path.join(TEMP_EXTRACT, os.path.basename(blendfile_src))

    stdout_src, stderr_src, returncode = run(args_blender_read_paths(blendfile_src))
    if returncode != BLENDER_EXIT_CODE:
        log.error("Python exception running blender!")
        cleanup()
        return True

    data_src = json_from_file(FILE_OUT)
    os.remove(FILE_OUT)

    stdout_dst, stderr_dst, returncode = run(args_blender_read_paths(blendfile_dst))
    if returncode != BLENDER_EXIT_CODE:
        log.error("Python exception running blender! (aborting this file!)")
        cleanup()
        return True

    data_dst = json_from_file(FILE_OUT)
    os.remove(FILE_OUT)

    shutil.rmtree(TEMP_EXTRACT)
    del returncode

    is_error = False

    # just extra check... not essential but means we know quickly if library state is different
    if stdout_src.count(b'LIB ERROR') != stdout_dst.count(b'LIB ERROR'):
        log.error("Library errors differ in packed library, with the following output")
        log.error("*** SOURCE STDOUT ***\n" + stdout_src.decode('utf-8'))
        log.error("*** PACKED STDOUT ***\n" + stdout_dst.decode('utf-8'))
        is_error = True

    data_src_basename = {os.path.basename(f_full): (f_full, f_ok) for f_full, f_ok in data_src}
    data_dst_basename = {os.path.basename(f_full): (f_full, f_ok) for f_full, f_ok in data_dst}

    # do magic!
    for f_src_nameonly, (f_src_full, f_src_ok) in data_src_basename.items():
        if f_src_ok:
            f_dst_full, f_dst_ok = data_dst_basename[f_src_nameonly]
            if not f_dst_ok:
                log.error("%r (%r -> %r) failed!" % (blendfile_src, f_src_full, f_dst_full))
                is_error = True
            else:
                # log.info("found %r -> %r" % (f_src_full, f_dst_full))
                pass

    return is_error


def pack_blend_recursive_test(
        paths,
        log,
        blender_bin="blender",
        ):
    num_blend = 0
    num_blend_fail = 0
    for path in paths:
        for f in iter_blends(path):
            try:
                is_error = pack_blend_test(f, log, blender_bin)
            except Exception as e:
                log.exception(e)
                is_error = True

            num_blend_fail += is_error
            num_blend += 1

            log.info("tally, %d blends, %d failed" % (num_blend, num_blend_fail))


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
    import logging

    logging.basicConfig(level=logging.DEBUG)
    log = logging.getLogger("PACK")
    log.setLevel(logging.DEBUG)

    if argv is None:
        argv = sys.argv[1:]

    parser = create_argparse()
    args = parser.parse_args(argv)

    pack_blend_recursive_test(
            args.paths,
            log,
            blender_bin=args.blender_bin or "blender",
            )


if __name__ == "__main__":
    main()
