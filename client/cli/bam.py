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
Blender asset manager
"""


# ------------------
# Ensure module path
import os
import sys
path = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "modules"))
if path not in sys.path:
    sys.path.append(path)
del os, sys, path
# --------

import logging
log = logging.getLogger("bam_cli")

# if we're a module, don't mess with logging level
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)


def fatal(msg):
    if __name__ == "__main__":
        import sys
        sys.stderr.write("fatal: ")
        sys.stderr.write(msg)
        sys.stderr.write("\n")
        sys.exit(1)
    else:
        raise RuntimeError(msg)


class bam_config:
    # fake module
    __slots__ = ()

    def __new__(cls, *args, **kwargs):
        raise RuntimeError("%s should not be instantiated" % cls)

    CONFIG_DIR = ".bam"
    # can infact be any file in the session
    SESSION_FILE = ".bam_paths_remap.json"

    @staticmethod
    def find_basedir(cwd=None, suffix=None, abort=False, test_subpath=CONFIG_DIR, descr="<unknown>"):
        """
        Return the config path (or None when not found)
        Actually should raise an error?
        """
        import os

        if cwd is None:
            cwd = os.getcwd()

        parent = (os.path.normpath(
                  os.path.abspath(
                  cwd)))

        parent_prev = None

        while parent != parent_prev:
            test_dir = os.path.join(parent, test_subpath)
            if os.path.exists(test_dir):
                if suffix is not None:
                    test_dir = os.path.join(test_dir, suffix)
                return test_dir

            parent_prev = parent
            parent = os.path.dirname(parent)

        if abort is True:
            fatal("Not a %s (or any of the parent directories): %s" % (descr, test_subpath))

        return None

    @staticmethod
    def find_rootdir(cwd=None, suffix=None, abort=False, test_subpath=CONFIG_DIR, descr="<unknown>"):
        """
        find_basedir(), without '.bam' suffix
        """
        path = bam_config.find_basedir(
                cwd=cwd,
                suffix=suffix,
                abort=abort,
                test_subpath=test_subpath,
                )

        return path[:-(len(test_subpath) + 1)]

    def find_sessiondir(cwd=None, abort=False):
        """
        from:  my_bam/my_session/some/subdir
        to:    my_bam/my_session
        where: my_bam/.bam/  (is the basedir)
        """
        session_rootdir = bam_config.find_basedir(
                cwd=cwd,
                test_subpath=bam_config.SESSION_FILE,
                abort=abort,
                descr="bam session"
                )
        return session_rootdir[:-len(bam_config.SESSION_FILE)]

    @staticmethod
    def load(id_="config", cwd=None, abort=False):
        filepath = bam_config.find_basedir(
                cwd=cwd,
                suffix=id_,
                descr="bam repository",
                )
        if abort is True:
            if filepath is None:
                fatal("Not a bam repository (or any of the parent directories): .bam")

        with open(filepath, 'r') as f:
            import json
            return json.load(f)

    @staticmethod
    def write(id_="config", data=None, cwd=None):
        filepath = bam_config.find_basedir(
                cwd=cwd,
                suffix=id_,
                descr="bam repository",
                )

        with open(filepath, 'w') as f:
            import json
            json.dump(
                    data, f, ensure_ascii=False,
                    check_circular=False,
                    # optional (pretty)
                    sort_keys=True, indent=4, separators=(',', ': '),
                    )

    @staticmethod
    def create_bamignore_filter(id_=".bamignore", cwd=None):
        path = bam_config.find_rootdir()
        import os
        bamignore = os.path.join(path, id_)
        if os.path.isfile(bamignore):
            with open(bamignore, 'r', encoding='utf-8') as f:
                compiled_patterns = []

                import re
                for i, l in enumerate(f):
                    l = l.rstrip()
                    if l:
                        try:
                            p = re.compile(l)
                        except re.error as e:
                            fatal("%s:%d file contains an invalid regular expression, %s" %
                                  (bamignore, i + 1, str(e)))
                        compiled_patterns.append(p)

                if compiled_patterns:
                    def filter_ignore(f):
                        for pattern in filter_ignore.compiled_patterns:
                            if re.match(pattern, f):
                                return False
                        return True
                    filter_ignore.compiled_patterns = compiled_patterns

                    return filter_ignore

        return None


class bam_session:
    # fake module
    __slots__ = ()

    def __new__(cls, *args, **kwargs):
        raise RuntimeError("%s should not be instantiated" % cls)

    @staticmethod
    def request_url(req_path):
        cfg = bam_config.load()
        result = "%s/%s" % (cfg['url'], req_path)
        return result

    @staticmethod
    def status(session_rootdir,
               paths_add, paths_remove, paths_modified, paths_remap_subset_add,
               paths_uuid_update=None):

        assert(isinstance(paths_add, dict))
        assert(isinstance(paths_remove, dict))
        assert(isinstance(paths_modified, dict))
        assert(isinstance(paths_remap_subset_add, dict))

        import os
        from bam_utils.system import sha1_from_file

        session_rootdir = os.path.abspath(session_rootdir)

        # don't commit metadata
        paths_used = {
            os.path.join(session_rootdir, ".bam_paths_uuid.json"),
            os.path.join(session_rootdir, ".bam_paths_remap.json"),
            os.path.join(session_rootdir, ".bam_deps_remap.json"),
            os.path.join(session_rootdir, ".bam_tmp.zip"),
            }

        with open(os.path.join(session_rootdir, ".bam_paths_uuid.json"), 'r') as f:
            import json
            paths_uuid = json.load(f)
            del json

        for f_rel, sha1 in paths_uuid.items():
            f_abs = os.path.join(session_rootdir, f_rel)
            if os.path.exists(f_abs):
                sha1_modified = sha1_from_file(f_abs)
                if sha1_modified != sha1:
                    paths_modified[f_rel] = f_abs
                if paths_uuid_update is not None:
                    paths_uuid_update[f_rel] = sha1_modified
                paths_used.add(f_abs)
            else:
                paths_remove[f_rel] = f_abs

        # ----
        # find new files
        def iter_files(path, filename_check=None):
            for dirpath, dirnames, filenames in os.walk(path):

                # skip '.svn'
                if dirpath.startswith(".") and dirpath != ".":
                    continue

                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if filename_check is None or filename_check(filepath):
                        yield filepath

        bamignore_filter = bam_config.create_bamignore_filter()

        # -----
        # read our path relative to the project path
        with open(os.path.join(session_rootdir, ".bam_paths_remap.json"), 'r') as f:
            import json
            paths_remap = json.load(f)
            paths_remap_relbase = paths_remap.get(".", "")

        for f_abs in iter_files(session_rootdir, bamignore_filter):
            if f_abs not in paths_used:
                # we should be clever - add the file to a useful location based on some rules
                # (category, filetype & tags?)

                f_rel = os.path.relpath(f_abs, session_rootdir)

                # remap paths of added files
                if f_rel.startswith("_"):
                    f_rel = f_rel[1:]
                else:
                    if paths_remap_relbase:
                        f_rel = os.path.join(paths_remap_relbase, f_rel)

                paths_add[f_rel] = f_abs

                if paths_uuid_update is not None:
                    paths_uuid_update[f_rel] = sha1_from_file(f_abs)

                # TESTING ONLY
                f_abs_remote = f_rel

                paths_remap_subset_add[f_rel] = f_abs_remote


class bam_commands:
    """
    Sub-commands from the command-line map directly to these methods.
    """
    # fake module
    __slots__ = ()

    def __new__(cls, *args, **kwargs):
        raise RuntimeError("%s should not be instantiated" % cls)

    @staticmethod
    def init(url, directory_name=None):
        import os
        import urllib.parse

        if "@" in url:
            # first & last :)
            username, url = url.rpartition('@')[0::2]
        else:
            import getpass
            username = getpass.getuser()
            print("Using username:", username)
            del getpass

        parsed_url = urllib.parse.urlsplit(url)

        proj_dirname = os.path.basename(parsed_url.path)
        if directory_name:
            proj_dirname = directory_name
        proj_dirname_abs = os.path.join(os.getcwd(), proj_dirname)

        if os.path.exists(proj_dirname_abs):
            fatal("Cannot create project %r already exists" % proj_dirname_abs)

        # Create the project directory inside the current directory
        os.mkdir(proj_dirname_abs)
        # Create the .bam directory
        bam_basedir = os.path.join(proj_dirname_abs, bam_config.CONFIG_DIR)
        os.mkdir(bam_basedir)

        # Add a config file with project url, username and password
        bam_config.write(
                data={
                    "url": url,
                    "user": username,
                    "password": "",
                    "config_version": 1
                    },
                cwd=proj_dirname_abs)

        print("Project %r initialized" % proj_dirname)

    @staticmethod
    def create(session_name):
        import os

        rootdir = bam_config.find_rootdir(abort=True)

        session_rootdir = os.path.join(rootdir, session_name)

        if os.path.exists(session_rootdir):
            fatal("session path exists %r" % session_rootdir)
        if rootdir != bam_config.find_rootdir(cwd=session_rootdir):
            fatal("session is located outside %r" % rootdir)

        def write_empty(f, data):
            with open(os.path.join(session_rootdir, f), 'wb') as f:
                f.write(data)

        os.makedirs(session_rootdir)

        write_empty(".bam_paths_uuid.json", b'{}')
        write_empty(".bam_paths_remap.json", b'{}')
        write_empty(".bam_deps_remap.json", b'{}')

        print("Session %r created" % session_name)

    @staticmethod
    def checkout(path, output_dir=None):
        import sys
        import os
        import requests

        cfg = bam_config.load(abort=True)

        if output_dir is None:
            # fallback to the basename
            dst_dir = os.path.splitext(os.path.basename(path))[0]
        else:
            output_dir = os.path.realpath(output_dir)
            if os.sep in output_dir.rstrip(os.sep):
                # are we a subdirectory?
                # (we know this exists, since we have config already)
                rootdir = bam_config.find_rootdir(abort=True)
                if ".." in os.path.relpath(output_dir, rootdir).split(os.sep):
                    fatal("Output %r is outside the project path %r" % (output_dir, rootdir))
                del rootdir
            dst_dir = output_dir
        del output_dir

        payload = {
            "filepath": path,
            "command": "checkout",
            }
        r = requests.get(
                bam_session.request_url("file"),
                params=payload,
                auth=(cfg['user'], cfg['password']),
                stream=True,
                )

        if r.status_code not in {200, }:
            # TODO(cam), make into reusable function?
            print("Error %d:\n%s" % (r.status_code, next(r.iter_content(chunk_size=1024)).decode('utf-8')))
            return

        # TODO(cam) how to tell if we get back a message payload? or real data???
        dst_dir_data = payload['filepath'].split('/')[-1]

        if 1:
            dst_dir_data += ".zip"

        with open(dst_dir_data, 'wb') as f:
            import struct
            ID_MESSAGE = 1
            ID_PAYLOAD = 2
            head = r.raw.read(4)
            if head != b'BAM\0':
                fatal("bad header from server")

            while True:
                msg_type, msg_size = struct.unpack("<II", r.raw.read(8))
                if msg_type == ID_MESSAGE:
                    sys.stdout.write(r.raw.read(msg_size).decode('utf-8'))
                    sys.stdout.flush()
                elif msg_type == ID_PAYLOAD:
                    # payload
                    break

            tot_size = 0
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:  # filter out keep-alive new chunks
                    tot_size += len(chunk)
                    f.write(chunk)
                    f.flush()

                    sys.stdout.write("\rdownload: [%03d%%]" % ((100 * tot_size) // msg_size))
                    sys.stdout.flush()

        # ---------------
        # extract the zip
        import zipfile
        with open(dst_dir_data, 'rb') as zip_file:
            zip_handle = zipfile.ZipFile(zip_file)
            zip_handle.extractall(dst_dir)
        del zipfile, zip_file

        os.remove(dst_dir_data)

        sys.stdout.write("\nwritten: %r\n" % dst_dir)

    @staticmethod
    def commit(paths, message):
        import os
        import requests

        # Load project configuration
        cfg = bam_config.load(abort=True)

        # TODO(cam) ignore files

        # TODO(cam) multiple paths
        session_rootdir = paths[0]

        if not os.path.isdir(session_rootdir):
            fatal("Expected a directory (%r)" % session_rootdir)

        basedir = bam_config.find_basedir(
                cwd=session_rootdir,
                descr="bam repository",
                )
        basedir_temp = os.path.join(basedir, "tmp")

        if os.path.isdir(basedir_temp):
            fatal("Path found, "
                  "another commit in progress, or remove with path! (%r)" %
                  basedir_temp)

        if not os.path.exists(os.path.join(session_rootdir, ".bam_paths_uuid.json")):
            fatal("Path not a project session, (%r)" %
                  session_rootdir)

        # make a zipfile from session
        import json
        with open(os.path.join(session_rootdir, ".bam_paths_uuid.json")) as f:
            paths_uuid = json.load(f)

        with open(os.path.join(session_rootdir, ".bam_deps_remap.json")) as f:
            deps_remap = json.load(f)

        paths_add = {}
        paths_modified = {}
        paths_remove = {}
        paths_remap_subset_add = {}
        paths_uuid_update = {}

        bam_session.status(
                session_rootdir,
                paths_add, paths_remove, paths_modified, paths_remap_subset_add,
                paths_uuid_update,
                )

        if not any((paths_add, paths_modified, paths_remove)):
            print("Nothing to commit!")
            return

        for f_rel, f_abs in list(paths_modified.items()):
            # we may want to be more clever here
            deps = deps_remap.get(f_rel)
            if deps:
                # ----
                # Remap!
                f_abs_remap = os.path.join(basedir_temp, f_rel)
                dir_remap = os.path.dirname(f_abs_remap)
                os.makedirs(dir_remap, exist_ok=True)

                import blendfile_pack_restore
                blendfile_pack_restore.blendfile_remap(
                        f_abs.encode('utf-8'),
                        dir_remap.encode('utf-8'),
                        deps,
                        )
                if os.path.exists(f_abs_remap):
                    f_abs = f_abs_remap

                    paths_modified[f_rel] = f_abs

        # -------------------------
        print("Now make a zipfile")
        import zipfile
        temp_zip = os.path.join(session_rootdir, ".bam_tmp.zip")
        with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zip_handle:
            for paths_dict, op in ((paths_modified, 'M'), (paths_add, 'A')):
                for (f_rel, f_abs) in paths_dict.items():
                    print("  packing (%s): %r" % (op, f_abs))
                    zip_handle.write(f_abs, arcname=f_rel)

            # make a paths remap that only includes modified files
            # TODO(cam), from 'packer.py'
            def write_dict_as_json(f, dct):
                zip_handle.writestr(
                        f,
                        json.dumps(dct,
                        check_circular=False,
                        # optional (pretty)
                        sort_keys=True, indent=4, separators=(',', ': '),
                        ).encode('utf-8'))

            with open(os.path.join(session_rootdir, ".bam_paths_remap.json")) as f:
                paths_remap = json.load(f)

            paths_remap_subset = {k: v for k, v in paths_remap.items() if k in paths_modified}
            paths_remap_subset.update(paths_remap_subset_add)
            write_dict_as_json(".bam_paths_remap.json", paths_remap_subset)

            # build a list of path manipulation operations
            paths_ops = {}
            # paths_remove ...
            for f_rel, f_abs in paths_remove.items():
                # TODO
                f_abs_remote = paths_remap[f_rel]
                paths_ops[f_abs_remote] = 'D'

            write_dict_as_json(".bam_paths_ops.json", paths_ops)
            log.debug(paths_ops)

        if os.path.exists(basedir_temp):
            import shutil
            shutil.rmtree(basedir_temp)
            del shutil

        # --------------
        # Commit Request
        args = {
            'message': message,
            }
        payload = {
            'command': 'commit',
            'arguments': json.dumps(args),
            }
        files = {
            'file': open(temp_zip, 'rb'),
            }

        r = requests.put(
                bam_session.request_url("file"),
                params=payload,
                auth=(cfg['user'], cfg['password']),
                files=files)

        files['file'].close()
        os.remove(temp_zip)

        try:
            r_json = r.json()
            print(r_json.get("message", "<empty>"))
        except Exception:
            print(r.text)

        # TODO, handle error cases
        ok = True
        if ok:
            # NOTE, we may want to generalize the 'update uuid' code & share it.

            paths_uuid.update(paths_uuid_update)
            with open(os.path.join(session_rootdir, ".bam_paths_uuid.json"), 'w') as f:
                json.dump(
                        paths_uuid_update, f, ensure_ascii=False,
                        check_circular=False,
                        # optional (pretty)
                        sort_keys=True, indent=4, separators=(',', ': '),
                        )

    @staticmethod
    def status(paths, use_json=False):
        # TODO(cam) multiple paths
        path = paths[0]
        del paths

        session_rootdir = bam_config.find_sessiondir(path, abort=True)

        paths_add = {}
        paths_modified = {}
        paths_remove = {}
        paths_remap_subset_add = {}

        bam_session.status(
                session_rootdir,
                paths_add, paths_remove, paths_modified, paths_remap_subset_add,
                )

        if not use_json:
            for f in sorted(paths_add):
                print("  A: %s" % f)
            for f in sorted(paths_modified):
                print("  M: %s" % f)
            for f in sorted(paths_remove):
                print("  D: %s" % f)
        else:
            ret = []
            for f in sorted(paths_add):
                ret.append(("A", f))
            for f in sorted(paths_modified):
                ret.append(("M", f))
            for f in sorted(paths_remove):
                ret.append(("D", f))

            import json
            print(json.dumps(ret))

    @staticmethod
    def list_dir(paths, use_json=False):
        import requests

        # Load project configuration
        cfg = bam_config.load(abort=True)

        # TODO(cam) multiple paths
        path = paths[0]
        del paths

        payload = {
            "path": path,
            }
        r = requests.get(
                bam_session.request_url("file_list"),
                params=payload,
                auth=(cfg['user'], cfg['password']),
                stream=True,
                )

        r_json = r.json()
        items = r_json.get("items_list")
        if items is None:
            fatal(r_json.get("message", "<empty>"))

        items.sort()

        if use_json:
            ret = []
            for (name_short, name_full, file_type) in items:
                ret.append((name_short, file_type))

            import json
            print(json.dumps(ret))
        else:
            for (name_short, name_full, file_type) in items:
                if file_type == "dir":
                    print("  %s/" % name_short)
            for (name_short, name_full, file_type) in items:
                if file_type != "dir":
                    print("  %s" % name_short)

    @staticmethod
    def deps(paths, recursive=False, use_json=False):
        import os

        def deps_path_walker():
            import blendfile_path_walker
            for blendfile_src in paths:
                blendfile_src = blendfile_src.encode('utf-8')
                yield from blendfile_path_walker.FilePath.visit_from_blend(
                        blendfile_src,
                        readonly=True,
                        recursive=recursive,
                        )

        def status_walker():
            for fp, (rootdir, fp_blend_basename) in deps_path_walker():
                f_rel = fp.filepath
                f_abs = fp.filepath_absolute

                yield (
                    # blendfile-src
                    os.path.join(fp.basedir, fp_blend_basename).decode('utf-8'),
                    # fillepath-dst
                    f_rel.decode('utf-8'),
                    f_abs.decode('utf-8'),
                    # filepath-status
                    "OK" if os.path.exists(f_abs) else "MISSING FILE",
                    )

        if use_json:
            import json
            is_first = True
            # print in parts, so we don't block the output
            print("[")
            for f_src, f_dst, f_dst_abs, f_status in status_walker():
                if is_first:
                    is_first = False
                else:
                    print(",")

                print(json.dumps((f_src, f_dst, f_dst_abs, f_status)), end="")
            print("]")
        else:
            for f_src, f_dst, f_dst_abs, f_status in status_walker():
                print("  %r -> (%r = %r) %s" % (f_src, f_dst, f_dst_abs, f_status))

# -----------------------------------------------------------------------------
# Argument Parser

def init_argparse_common(
        subparse,
        use_json=False,
        ):
    if use_json:
        subparse.add_argument(
                "-j", "--json", dest="json", action='store_true',
                help="Generate JSON output",
                )


def create_argparse_init(subparsers):
    subparse = subparsers.add_parser("init")
    subparse.add_argument(
            dest="url",
            help="Project repository url",
            )
    subparse.add_argument(
            dest="directory_name", nargs="?",
            help="Directory name",
            )
    subparse.set_defaults(
            func=lambda args:
            bam_commands.init(args.url, args.directory_name),
            )


def create_argparse_create(subparsers):
    subparse = subparsers.add_parser(
            "create", aliases=("cr",),
            help="Create a new empty session directory",
            )
    subparse.add_argument(
            dest="session_name", nargs=1,
            help="Name of session directory",
            )
    subparse.set_defaults(
            func=lambda args:
            bam_commands.create(args.session_name[0]),
            )


def create_argparse_checkout(subparsers):
    subparse = subparsers.add_parser(
            "checkout", aliases=("co",),
            help="",
            )
    subparse.add_argument(
            dest="path", type=str, metavar='REMOTE_PATH',
            help="Path to checkout on the server",
            )
    subparse.add_argument(
            "-o", "--output", dest="output", type=str, metavar='DIRNAME',
            help="Local name to checkout the session into (optional, falls back to path name)",
            )
    subparse.set_defaults(
            func=lambda args:
            bam_commands.checkout(args.path, args.output),
            )


def create_argparse_commit(subparsers):
    subparse = subparsers.add_parser(
            "commit", aliases=("ci",),
            help="",
            )
    subparse.add_argument(
            "-m", "--message", dest="message", metavar='MESSAGE',
            required=True,
            help="Commit message",
            )
    subparse.add_argument(
            dest="paths", nargs="*",
            help="paths to commit",
            )
    subparse.set_defaults(
            func=lambda args:
            bam_commands.commit(args.paths or ["."], args.message),
            )


def create_argparse_update(subparsers):
    subparse = subparsers.add_parser(
            "update", aliases=("up",),
            help="",
            )
    subparse.add_argument(
            dest="paths", nargs="+",
            help="Path(s) to operate on",
            )
    subparse.set_defaults(
            func=lambda args:
            # TODO
            print(args),
            )


def create_argparse_revert(subparsers):
    subparse = subparsers.add_parser(
            "revert", aliases=("rv",),
            help="",
            )
    subparse.add_argument(
            dest="paths", nargs="+",
            help="Path(s) to operate on",
            )
    subparse.set_defaults(
            func=lambda args:
            # TODO
            print(args)
            )


def create_argparse_status(subparsers):
    subparse = subparsers.add_parser(
            "status", aliases=("st",),
            help="",
            )
    subparse.add_argument(
            dest="paths", nargs="*",
            help="Path(s) to operate on",
            )

    init_argparse_common(subparse, use_json=True)

    subparse.set_defaults(
            func=lambda args:
            bam_commands.status(args.paths or ["."], use_json=args.json),
            )


def create_argparse_list(subparsers):
    subparse = subparsers.add_parser(
            "list", aliases=("ls",),
            help="",
            )
    subparse.add_argument(
            dest="paths", nargs="*",
            help="Path(s) to operate on",
            )

    init_argparse_common(subparse, use_json=True)

    subparse.set_defaults(
            func=lambda args:
            bam_commands.list_dir(
                    args.paths or ["."],
                    use_json=args.json),
                    )


def create_argparse_deps(subparsers):
    subparse = subparsers.add_parser(
            "deps", aliases=("dp",),
            help="",
            )
    subparse.add_argument(
            dest="paths", nargs="*",
            help="Path(s) to operate on",
            )
    subparse.add_argument(
            "-r", "--recursive", dest="recursive", action='store_true',
            help="Scan dependencies recursively",
            )

    init_argparse_common(subparse, use_json=True)

    subparse.set_defaults(
            func=lambda args:
            bam_commands.deps(
                    args.paths or ["."], args.recursive,
                    use_json=args.json),
                    )


def create_argparse():
    import argparse

    usage_text = (
        "BAM! (Blender Asset Manager)\n" +
        __doc__
        )

    parser = argparse.ArgumentParser(description=usage_text)

    subparsers = parser.add_subparsers(
            title='subcommands',
            description='valid subcommands',
            help='additional help',
            )

    create_argparse_init(subparsers)
    create_argparse_create(subparsers)
    create_argparse_checkout(subparsers)
    create_argparse_commit(subparsers)
    create_argparse_update(subparsers)
    create_argparse_revert(subparsers)
    create_argparse_status(subparsers)
    create_argparse_list(subparsers)
    create_argparse_deps(subparsers)

    return parser


def main(argv=None):

    if argv is None:
        import sys
        argv = sys.argv[1:]

    parser = create_argparse()
    args = parser.parse_args(argv)

    # call subparser callback
    if not hasattr(args, "func"):
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
