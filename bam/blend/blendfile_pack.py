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

from bam.blend import blendfile_path_walker

TIMEIT = False

# ------------------
# Ensure module path
import os
import sys
path = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "modules"))
if path not in sys.path:
    sys.path.append(path)
del os, sys, path
# --------


# ----------------------
# debug low level output
#
# ... when internals _really_ fail & we want to know why
def _dbg(text):
    import sys
    from bam_utils.system import colorize
    if type(text) is bytes:
        text = text.decode('utf-8')
    sys.__stdout__.write(colorize(text, color='red') + "\n")
    sys.__stdout__.flush()


def _relpath_remap(
        path_src,
        base_dir_src,
        fp_basedir,
        blendfile_src_dir_fakeroot,
        ):

    import os

    if not os.path.isabs(path_src):
        # Absolute win32 paths on a unix system
        # cause bad issues!
        if len(path_src) >= 2:
            if path_src[0] != b'/'[0] and path_src[1] == b':'[0]:
                pass
            else:
                raise Exception("Internal error 'path_src' -> %r must be absolute" % path_src)

    path_src = os.path.normpath(path_src)
    path_dst = os.path.relpath(path_src, base_dir_src)

    if blendfile_src_dir_fakeroot is None:
        # /foo/../bar.png --> /foo/__/bar.png
        path_dst = path_dst.replace(b'..', b'__')
        path_dst = os.path.normpath(path_dst)
    else:
        if b'..' in path_dst:
            # remap, relative to project root

            # paths
            path_dst = os.path.join(blendfile_src_dir_fakeroot, path_dst)
            path_dst = os.path.normpath(path_dst)
            # if there are paths outside the root still...
            # This means they are outside the project directory, We dont support this,
            # so name accordingly
            if b'..' in path_dst:
                # SHOULD NEVER HAPPEN
                path_dst = path_dst.replace(b'..', b'__nonproject__')
            path_dst = b'_' + path_dst

    # _dbg(b"FINAL A: " + path_dst)
    path_dst_final = os.path.join(os.path.relpath(base_dir_src, fp_basedir), path_dst)
    path_dst_final = os.path.normpath(path_dst_final)
    # _dbg(b"FINAL B: " + path_dst_final)

    return path_dst, path_dst_final


def pack(
        # store the blendfile relative to this directory, can be:
        #    os.path.dirname(blendfile_src)
        # but in some cases we wan't to use a path higher up.
        # base_dir_src,
        blendfile_src, blendfile_dst, mode='FILE',
        paths_remap_relbase=None,
        deps_remap=None, paths_remap=None, paths_uuid=None,
        # load every libs dep, not just used deps.
        all_deps=False,
        compress_level=-1,
        # yield reports
        report=None,

        # The project path, eg:
        # /home/me/myproject/mysession/path/to/blend/file.blend
        # the path would be:         b'path/to/blend'
        #
        # This is needed so we can choose to store paths
        # relative to project or relative to the current file.
        #
        # When None, map _all_ paths are relative to the current blend.
        # converting:  '../../bar' --> '__/__/bar'
        # so all paths are nested and not moved outside the session path.
        blendfile_src_dir_fakeroot=None,
        ):
    """
    :param deps_remap: Store path deps_remap info as follows.
       {"file.blend": {"path_new": "path_old", ...}, ...}

    :type deps_remap: dict or None
    """

    # Internal details:
    # - we copy to a temp path before operating on the blend file
    #   so we can modify in-place.
    # - temp files are only created once, (if we never touched them before),
    #   this way, for linked libraries - a single blend file may be used
    #   multiple times, each access will apply new edits ontop of the old ones.
    # - we track which libs we have touched (using 'lib_visit' arg),
    #   this means that the same libs wont be touched many times to modify the same data
    #   also prevents cyclic loops from crashing.

    import os
    import shutil

    from bam.utils.system import colorize

    # in case this is directly from the command line or user-input
    blendfile_src = os.path.normpath(os.path.abspath(blendfile_src))
    blendfile_dst = os.path.normpath(os.path.abspath(blendfile_dst))

    # first check args are OK
    # fakeroot _cant_ start with a separator, since we prepend chars to it.
    assert((blendfile_src_dir_fakeroot is None) or
           (not blendfile_src_dir_fakeroot.startswith(os.sep.encode('ascii'))))

    path_temp_files = set()
    path_copy_files = set()

    TEMP_SUFFIX = b'@'

    if report is None:
        report = lambda msg: msg

    yield report("%s: %r...\n" % (colorize("\nscanning deps", color='bright_green'), blendfile_src))

    if TIMEIT:
        import time
        t = time.time()

    base_dir_src = os.path.dirname(blendfile_src)
    base_dir_dst = os.path.dirname(blendfile_dst)
    # _dbg(blendfile_src)
    # _dbg(blendfile_dst)

    if mode == 'ZIP':
        base_dir_dst_temp = os.path.join(base_dir_dst, b'__blendfile_temp__')
    else:
        base_dir_dst_temp = os.path.join(base_dir_dst, b'__blendfile_pack__')

    def temp_remap_cb(filepath, rootdir):
        """
        Create temp files in the destination path.
        """
        filepath = blendfile_path_walker.utils.compatpath(filepath)

        # first remap this blend file to the location it will end up (so we can get images relative to _that_)
        # TODO(cam) cache the results
        fp_basedir_conv = _relpath_remap(os.path.join(rootdir, b'dummy'), base_dir_src, base_dir_src, blendfile_src_dir_fakeroot)[0]
        fp_basedir_conv = os.path.join(base_dir_src, os.path.dirname(fp_basedir_conv))

        # then get the file relative to the new location
        filepath_tmp = _relpath_remap(filepath, base_dir_src, fp_basedir_conv, blendfile_src_dir_fakeroot)[0]
        filepath_tmp = os.path.normpath(os.path.join(base_dir_dst_temp, filepath_tmp)) + TEMP_SUFFIX

        # only overwrite once (so we can write into a path already containing files)
        if filepath_tmp not in path_temp_files:
            os.makedirs(os.path.dirname(filepath_tmp), exist_ok=True)
            shutil.copy(filepath, filepath_tmp)
            path_temp_files.add(filepath_tmp)
        return filepath_tmp

    lib_visit = {}
    fp_blend_basename_last = b''

    for fp, (rootdir, fp_blend_basename) in blendfile_path_walker.FilePath.visit_from_blend(
            blendfile_src,
            readonly=False,
            temp_remap_cb=temp_remap_cb,
            recursive=True,
            recursive_all=all_deps,
            lib_visit=lib_visit,
            ):

        # we could pass this in!
        fp_blend = os.path.join(fp.basedir, fp_blend_basename)

        if fp_blend_basename_last != fp_blend_basename:
            yield report("  %s:       %s\n" % (colorize("blend", color='blue'), fp_blend))
            fp_blend_basename_last = fp_blend_basename

        # assume the path might be relative
        path_src_orig = fp.filepath
        path_rel = blendfile_path_walker.utils.compatpath(path_src_orig)
        path_src = blendfile_path_walker.utils.abspath(path_rel, fp.basedir)
        path_src = os.path.normpath(path_src)

        # destination path realtive to the root
        # assert(b'..' not in path_src)
        assert(b'..' not in base_dir_src)

        # first remap this blend file to the location it will end up (so we can get images relative to _that_)
        # TODO(cam) cache the results
        fp_basedir_conv = _relpath_remap(fp_blend, base_dir_src, base_dir_src, blendfile_src_dir_fakeroot)[0]
        fp_basedir_conv = os.path.join(base_dir_src, os.path.dirname(fp_basedir_conv))

        # then get the file relative to the new location
        path_dst, path_dst_final = _relpath_remap(path_src, base_dir_src, fp_basedir_conv, blendfile_src_dir_fakeroot)

        path_dst = os.path.join(base_dir_dst, path_dst)

        path_dst_final = b'//' + path_dst_final
        fp.filepath = path_dst_final

        # add to copy-list
        # never copy libs (handled separately)
        if not isinstance(fp, blendfile_path_walker.FPElem_block_path) or fp.userdata[0].code != b'LI':
            path_copy_files.add((path_src, path_dst))

            for file_list in (
                    blendfile_path_walker.utils.find_sequence_paths(path_src) if fp.is_sequence else (),
                    fp.files_siblings(),
                    ):

                _src_dir = os.path.dirname(path_src)
                _dst_dir = os.path.dirname(path_dst)
                path_copy_files.update(
                        {(os.path.join(_src_dir, f), os.path.join(_dst_dir, f))
                        for f in file_list
                        })
                del _src_dir, _dst_dir

        if deps_remap is not None:
            # this needs to become JSON later... ugh, need to use strings
            deps_remap.setdefault(
                    fp_blend_basename.decode('utf-8'),
                    {})[path_dst_final.decode('utf-8')] = path_src_orig.decode('utf-8')

    del lib_visit, fp_blend_basename_last

    if TIMEIT:
        print("  Time: %.4f\n" % (time.time() - t))

    yield report(("%s: %d files\n") %
                 (colorize("\narchiving", color='bright_green'), len(path_copy_files) + 1))

    # handle deps_remap and file renaming
    if deps_remap is not None:
        blendfile_src_basename = os.path.basename(blendfile_src).decode('utf-8')
        blendfile_dst_basename = os.path.basename(blendfile_dst).decode('utf-8')

        if blendfile_src_basename != blendfile_dst_basename:
            if mode != 'ZIP':
                deps_remap[blendfile_dst_basename] = deps_remap[blendfile_src_basename]
                del deps_remap[blendfile_src_basename]
        del blendfile_src_basename, blendfile_dst_basename

    # store path mapping {dst: src}
    if paths_remap is not None:

        if paths_remap_relbase is not None:
            relbase = lambda fn: os.path.relpath(fn, paths_remap_relbase)
        else:
            relbase = lambda fn: fn

        for src, dst in path_copy_files:
            # TODO. relative to project-basepath
            paths_remap[os.path.relpath(dst, base_dir_dst).decode('utf-8')] = relbase(src).decode('utf-8')
        # main file XXX, should have better way!
        paths_remap[os.path.basename(blendfile_src).decode('utf-8')] = relbase(blendfile_src).decode('utf-8')

        del relbase

    if paths_uuid is not None:
        from bam.utils.system import uuid_from_file

        for src, dst in path_copy_files:
            paths_uuid[os.path.relpath(dst, base_dir_dst).decode('utf-8')] = uuid_from_file(src)
        # XXX, better way to store temp target
        blendfile_dst_tmp = temp_remap_cb(blendfile_src, base_dir_src)
        paths_uuid[os.path.basename(blendfile_src).decode('utf-8')] = uuid_from_file(blendfile_dst_tmp)

        # blend libs
        for dst in path_temp_files:
            k = os.path.relpath(dst[:-len(TEMP_SUFFIX)], base_dir_dst_temp).decode('utf-8')
            if k not in paths_uuid:
                paths_uuid[k] = uuid_from_file(dst)
            del k

        del blendfile_dst_tmp
        del uuid_from_file

    # --------------------
    # Handle File Copy/Zip

    if mode == 'FILE':
        blendfile_dst_tmp = temp_remap_cb(blendfile_src, base_dir_src)

        shutil.move(blendfile_dst_tmp, blendfile_dst)
        path_temp_files.remove(blendfile_dst_tmp)

        # strip TEMP_SUFFIX
        for fn in path_temp_files:
            shutil.move(fn, fn[:-1])

        for src, dst in path_copy_files:
            assert(b'.blend' not in dst)

            if not os.path.exists(src):
                yield report("  %s: %r\n" % (colorize("source missing", color='red'), src))
            else:
                yield report("  %s: %r -> %r\n" % (colorize("copying", color='blue'), src, dst))
                shutil.copy(src, dst)

        yield report("  %s: %r\n" % (colorize("written", color='green'), blendfile_dst))

    elif mode == 'ZIP':
        import zipfile

        # not awesome!
        import zlib
        assert(compress_level in range(-1, 10))
        _compress_level_orig = zlib.Z_DEFAULT_COMPRESSION
        zlib.Z_DEFAULT_COMPRESSION = compress_level
        _compress_mode = zipfile.ZIP_DEFLATED (compress_level == 0) if zipfile.ZIP_STORED else zipfile.ZIP_DEFLATED

        with zipfile.ZipFile(blendfile_dst.decode('utf-8'), 'w', _compress_mode) as zip_handle:
            for fn in path_temp_files:
                yield report("  %s: %r -> <archive>\n" % (colorize("copying", color='blue'), fn))
                zip_handle.write(
                        fn.decode('utf-8'),
                        arcname=os.path.relpath(fn[:-1], base_dir_dst_temp).decode('utf-8'))
                os.remove(fn)

            shutil.rmtree(base_dir_dst_temp)

            for src, dst in path_copy_files:
                assert(not dst.endswith(b'.blend'))

                if not os.path.exists(src):
                    yield report("  %s: %r\n" % (colorize("source missing", color='red'), src))
                else:
                    yield report("  %s: %r -> <archive>\n" % (colorize("copying", color='blue'), src))
                    zip_handle.write(src.decode('utf-8'),
                              arcname=os.path.relpath(dst, base_dir_dst).decode('utf-8'))

                    """
                    _dbg(b"")
                    _dbg(b"REAL_FILE:     " + dst)
                    _dbg(b"RELATIVE_FILE: " + os.path.relpath(dst, base_dir_dst))
                    """

        zlib.Z_DEFAULT_COMPRESSION = _compress_level_orig
        del _compress_level_orig, _compress_mode

        yield report("  %s: %r\n" % (colorize("written", color='green'), blendfile_dst))
    else:
        raise Exception("%s not a known mode" % mode)


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
            "-i", "--input", dest="path_src", metavar='FILE', required=True,
            help="Input path(s) or a wildcard to glob many files",
            )
    parser.add_argument(
            "-o", "--output", dest="path_dst", metavar='DIR', required=True,
            help="Output file or a directory when multiple inputs are passed",
            )
    parser.add_argument(
            "-m", "--mode", dest="mode", metavar='MODE', required=False,
            choices=('FILE', 'ZIP'), default='FILE',
            help="Output file or a directory when multiple inputs are passed",
            )
    parser.add_argument(
            "-q", "--quiet", dest="use_quiet", action='store_true', required=False,
            help="Suppress status output",
            )

    return parser


def main():
    import sys

    parser = create_argparse()
    args = parser.parse_args(sys.argv[1:])

    encoding = sys.getfilesystemencoding()

    if args.use_quiet:
        report = lambda msg: None
    else:
        report = lambda msg: print(msg, end="")

    for msg in pack(
            args.path_src.encode('utf-8'),
            args.path_dst.encode('utf-8'),
            mode=args.mode,
            ):
        report(msg)


if __name__ == "__main__":
    main()