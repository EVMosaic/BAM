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
Module for remapping paths from one directory to another.
"""

import os


# ----------------------------------------------------------------------------
# private utility functions

def _is_blend(f):
    return f.lower().endswith(b'.blend')


def _warn(msg):
    print("Warning: %s" % msg)


def _uuid_from_file(fn, block_size=1 << 20):
    with open(fn, 'rb') as f:
        # first get the size
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(0, os.SEEK_SET)
        # done!

        import hashlib
        sha1 = hashlib.new('sha512')
        while True:
            data = f.read(block_size)
            if not data:
                break
            sha1.update(data)
        return (hex(size)[2:] + sha1.hexdigest()).encode()


def _iter_files(paths, check_ext=None):
    for p in paths:
        p = os.path.abspath(p)
        for dirpath, dirnames, filenames in os.walk(p):
            # skip '.svn'
            if dirpath.startswith(b'.') and dirpath != b'.':
                continue

            for filename in filenames:
                if check_ext is None or check_ext(filename):
                    filepath = os.path.join(dirpath, filename)
                    yield filepath


# ----------------------------------------------------------------------------
# Public Functions

def start(
    paths,
    dry_run=False,
    ):
    # {(sha1, length): "filepath"}
    remap_uuid = {}

    # all files we need to map
    # absolute paths
    files_to_map = set()

    # TODO, validate paths aren't nested! ["/foo", "/foo/bar"]
    # it will cause problems touching files twice!

    # ------------------------------------------------------------------------
    # First walk over all blends
    import blendfile_path_walker

    for blendfile in _iter_files(paths, check_ext=_is_blend):
        for fp, (rootdir, fp_blend_basename) in blendfile_path_walker.FilePath.visit_from_blend(
                blendfile,
                readonly=True,
                recursive=False,
                ):
            # TODO. warn when referencing files outside 'paths'

            # so we can update the reference
            f_abs = fp.filepath_absolute
            f_abs = os.path.normpath(f_abs)
            if os.path.exists(f_abs):
                files_to_map.add(f_abs)
            else:
                _warn("file %r from %r not found!" % (f_abs, blendfile))

        # so we can know where its moved to
        files_to_map.add(blendfile)
    del blendfile_path_walker

    # ------------------------------------------------------------------------
    # Store UUID
    #
    # note, sorting is only to give predictable warnings/behavior
    for f in sorted(files_to_map):
        f_uuid = _uuid_from_file(f)

        f_match = remap_uuid.get(f_uuid)
        if f_match is not None:
            _warn("duplicate file found! (%r, %r)" % (f_match, f))

        remap_uuid[f_uuid] = f

    # now find all deps
    remap_data_args = (
            remap_uuid,
            )

    return remap_data_args


def finish(
    paths, remap_data_args,
    force_relative=False,
    dry_run=False,
    ):

    (remap_uuid,
     ) = remap_data_args

    remap_src_to_dst = {}
    remap_dst_to_src = {}

    for f_dst in _iter_files(paths):
        f_uuid = _uuid_from_file(f_dst)
        f_src = remap_uuid.get(f_uuid)
        if f_src is not None:
            remap_src_to_dst[f_src] = f_dst
            remap_dst_to_src[f_dst] = f_src

    # now the fun begins, remap _all_ paths
    import blendfile_path_walker


    for blendfile_dst in _iter_files(paths, check_ext=_is_blend):
        blendfile_src = remap_dst_to_src.get(blendfile_dst)
        if blendfile_src is None:
            _warn("new blendfile added since beginning 'remap': %r" % blendfile_dst)
            continue

        blendfile_src_basedir = os.path.dirname(blendfile_src)
        blendfile_dst_basedir = os.path.dirname(blendfile_dst)
        for fp, (rootdir, fp_blend_basename) in blendfile_path_walker.FilePath.visit_from_blend(
                blendfile_dst,
                readonly=False,
                recursive=False,
                ):
            # TODO. warn when referencing files outside 'paths'

            # so we can update the reference
            f_src_rel = fp.filepath
            is_relative = f_src_rel.startswith(b'//')
            if is_relative:
                f_src_abs = fp.filepath_absolute_resolve(basedir=blendfile_src_basedir)
            else:
                f_src_abs = f_src_rel

            f_src_abs = os.path.normpath(f_src_abs)
            f_dst_abs = remap_src_to_dst.get(f_src_abs)

            if f_dst_abs is None:
                _warn("file %r from %r not found in map!" % (f_src_abs, blendfile_dst))
                continue

            # now remap!
            if is_relative or force_relative:
                f_dst_rel = b'//' + os.path.relpath(f_dst_abs, blendfile_dst_basedir)
            else:
                f_dst_rel = f_dst_abs

            if f_dst_rel != f_src_rel:
                if not dry_run:
                    fp.filepath = f_dst_abs
                # print("remap %r -> %r" % (f_src_abs, fp.filepath))

    del blendfile_path_walker

