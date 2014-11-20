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
               paths_add, paths_remove, paths_modified, paths_remap_subset_add):

        assert(isinstance(paths_add, dict))
        assert(isinstance(paths_remove, dict))
        assert(isinstance(paths_modified, dict))
        assert(isinstance(paths_remap_subset_add, dict))

        import os
        from bam_utils.system import sha1_from_file

        # don't commit metadata
        paths_used = {
            os.path.join(session_rootdir, ".bam_paths_uuid.json"),
            os.path.join(session_rootdir, ".bam_paths_remap.json"),
            os.path.join(session_rootdir, ".bam_deps_remap.json"),
            os.path.join(session_rootdir, ".bam_tmp.zip"),
            }


        with open(os.path.join(session_rootdir, ".bam_paths_uuid.json")) as f:
            import json
            paths_uuid = json.load(f)
            del json

        for fn_rel, sha1 in paths_uuid.items():
            fn_abs = os.path.join(session_rootdir, fn_rel)
            if os.path.exists(fn_abs):
                if sha1_from_file(fn_abs) != sha1:
                    paths_modified[fn_rel] = fn_abs

                paths_used.add(fn_abs)
            else:
                paths_remove[fn_rel] = fn_abs

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

        def bamignore_check(fn):
            # TODO(cam)
            # .bamignore
            if fn.endswith(".blend1"):
                return False
            return True

        for fn_abs in iter_files(session_rootdir, bamignore_check):
            if fn_abs not in paths_used:
                # we should be clever - add the file to a useful location based on some rules
                # (category, filetype & tags?)
                fn_rel = os.path.basename(fn_abs)

                # TODO(cam)
                # remap paths of added files
                paths_add[fn_rel] = fn_abs

                # TESTING ONLY
                fn_abs_remote = fn_rel
                paths_remap_subset_add[fn_rel] = fn_abs_remote


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

        def write_empty(fn, data):
            with open(os.path.join(session_rootdir, fn), 'wb') as f:
                f.write(data)

        os.makedirs(session_rootdir)

        write_empty(".bam_paths_uuid.json", b'{}')
        write_empty(".bam_paths_remap.json", b'{}')
        write_empty(".bam_deps_remap.json", b'{}')

        print("Session %r created" % session_name)


    @staticmethod
    def checkout(paths):
        import sys
        import os
        import requests

        cfg = bam_config.load(abort=True)

        # TODO(cam) multiple paths
        path = paths[0]
        del paths

        # TODO(cam) we may want to checkout a single file? how to handle this?
        # we may want to checkout a dir too
        dst_dir = os.path.splitext(os.path.basename(path))[0]

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
                if chunk: # filter out keep-alive new chunks
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
        import sys
        import os
        import requests

        # Load project configuration
        cfg = bam_config.load(abort=True)

        # TODO(cam) ignore files

        # TODO(cam) multiple paths
        session_rootdir = paths[0]

        if not os.path.isdir(session_rootdir):
            print("Expected a directory (%r)" % session_rootdir)
            sys.exit(1)

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

        bam_session.status(
                session_rootdir,
                paths_add, paths_remove, paths_modified, paths_remap_subset_add,
                )

        if not paths_modified and not paths_add:
            print("Nothing to commit!")
            return


        for fn_rel, fn_abs in list(paths_modified.items()):
            # we may want to be more clever here
            deps = deps_remap.get(fn_rel)
            if deps:
                # ----
                # Remap!
                fn_abs_remap = os.path.join(basedir_temp, fn_rel)
                dir_remap = os.path.dirname(fn_abs_remap)
                os.makedirs(dir_remap, exist_ok=True)

                import blendfile_pack_restore
                blendfile_pack_restore.blendfile_remap(
                        fn_abs.encode('utf-8'),
                        dir_remap.encode('utf-8'),
                        deps,
                        )
                if os.path.exists(fn_abs_remap):
                    fn_abs = fn_abs_remap

                    paths_modified[fn_rel] = fn_abs

        # -------------------------
        print("Now make a zipfile")
        import zipfile
        temp_zip = os.path.join(session_rootdir, ".bam_tmp.zip")
        with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zip_handle:
            for paths_dict, op in ((paths_modified, 'M'), (paths_add, 'A')):
                for (fn_rel, fn_abs) in paths_dict.items():
                    print("  packing (%s): %r" % (op, fn_abs))
                    zip_handle.write(fn_abs, arcname=fn_rel)

            # make a paths remap that only includes modified files
            # TODO(cam), from 'packer.py'
            def write_dict_as_json(fn, dct):
                zip_handle.writestr(
                        fn,
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
            for fn_rel, fn_abs in paths_remove.items():
                # TODO
                fn_abs_remote = paths_remap[fn_rel]
                paths_ops[fn_abs_remote] = 'D'

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

        # TODO(cam)
        # if all goes well, rewrite sha1's


    @staticmethod
    def status(paths):
        # TODO(cam) multiple paths
        path = paths[0]
        del paths

        session_rootdir = bam_config.find_sessiondir(path, abort=True)
        print(session_rootdir)


        paths_add = {}
        paths_modified = {}
        paths_remove = {}
        paths_remap_subset_add = {}

        bam_session.status(session_rootdir, paths_add, paths_remove, paths_modified, paths_remap_subset_add)

        for fn in sorted(paths_add):
            print("  A: %s" % fn)
        for fn in sorted(paths_modified):
            print("  M: %s" % fn)
        for fn in sorted(paths_remove):
            print("  D: %s" % fn)

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
    def deps(paths, recursive=False):
        import blendfile_path_walker
        import os
        # TODO(cam) multiple paths
        for blendfile_src in paths:
            blendfile_src = blendfile_src.encode('utf-8')
            for fp, (rootdir, fp_blend_basename) in blendfile_path_walker.FilePath.visit_from_blend(
                    blendfile_src,
                    readonly=True,
                    recursive=recursive,
                    ):
                print("  %r -> %r" % (os.path.join(fp.basedir, fp_blend_basename), fp.filepath))


def subcommand_init_cb(args):
    bam_commands.init(args.url, args.directory_name)


def subcommand_create_cb(args):
    bam_commands.create(args.session_name[0])


def subcommand_checkout_cb(args):
    bam_commands.checkout(args.paths)


def subcommand_commit_cb(args):
    bam_commands.commit(args.paths or ["."], args.message)


def subcommand_update_cb(args):
    print(args)


def subcommand_revert_cb(args):
    print(args)


def subcommand_status_cb(args):
    bam_commands.status(args.paths or ["."])


def subcommand_list_cb(args):
    bam_commands.list_dir(args.paths or ["."], use_json=args.json)


def subcommand_deps_cb(args):
    bam_commands.deps(args.paths or ["."], args.recursive)


def generic_argument_json(subparse):
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
    subparse.set_defaults(func=subcommand_init_cb)


def create_argparse_create(subparsers):
    subparse = subparsers.add_parser(
            "create", aliases=("cr",),
            help="Create a new empty session directory",
            )
    subparse.add_argument(
            dest="session_name", nargs=1,
            help="Name of session directory",
            )
    subparse.set_defaults(func=subcommand_create_cb)


def create_argparse_checkout(subparsers):
    subparse = subparsers.add_parser(
            "checkout", aliases=("co",),
            help="",
            )
    subparse.add_argument(
            dest="paths", nargs="+",
            help="Path(s) to operate on",
            )
    subparse.set_defaults(func=subcommand_checkout_cb)


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

    subparse.set_defaults(func=subcommand_commit_cb)


def create_argparse_update(subparsers):
    subparse = subparsers.add_parser(
            "update", aliases=("up",),
            help="",
            )
    subparse.add_argument(
            dest="paths", nargs="+",
            help="Path(s) to operate on",
            )
    subparse.set_defaults(func=subcommand_update_cb)


def create_argparse_revert(subparsers):
    subparse = subparsers.add_parser(
            "revert", aliases=("rv",),
            help="",
            )
    subparse.add_argument(
            dest="paths", nargs="+",
            help="Path(s) to operate on",
            )
    subparse.set_defaults(func=subcommand_revert_cb)


def create_argparse_status(subparsers):
    subparse = subparsers.add_parser(
            "status", aliases=("st",),
            help="",
            )
    subparse.add_argument(
            dest="paths", nargs="*",
            help="Path(s) to operate on",
            )
    subparse.set_defaults(func=subcommand_status_cb)


def create_argparse_list(subparsers):
    subparse = subparsers.add_parser(
            "list", aliases=("ls",),
            help="",
            )
    subparse.add_argument(
            dest="paths", nargs="*",
            help="Path(s) to operate on",
            )

    generic_argument_json(subparse)

    subparse.set_defaults(func=subcommand_list_cb)


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
    subparse.set_defaults(func=subcommand_deps_cb)


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
