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

import os
import sys
import json

# ------------------
# Ensure module path
path = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "modules"))
if path not in sys.path:
    sys.path.append(path)
del path
# --------

import logging
log = logging.getLogger("bam_cli")

# if we're a module, don't mess with logging level
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)


def fatal(msg):
    if __name__ == "__main__":
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
    def find_basedir(cwd=None, path_suffix=None, abort=False, test_subpath=CONFIG_DIR, descr="<unknown>"):
        """
        Return the config path (or None when not found)
        Actually should raise an error?
        """

        if cwd is None:
            cwd = os.getcwd()

        parent = (os.path.normpath(
                  os.path.abspath(
                  cwd)))

        parent_prev = None

        while parent != parent_prev:
            test_dir = os.path.join(parent, test_subpath)
            if os.path.exists(test_dir):
                if path_suffix is not None:
                    test_dir = os.path.join(test_dir, path_suffix)
                return test_dir

            parent_prev = parent
            parent = os.path.dirname(parent)

        if abort is True:
            fatal("Not a %s (or any of the parent directories): %s" % (descr, test_subpath))

        return None

    @staticmethod
    def find_rootdir(cwd=None, path_suffix=None, abort=False, test_subpath=CONFIG_DIR, descr="<unknown>"):
        """
        find_basedir(), without '.bam' suffix
        """
        path = bam_config.find_basedir(
                cwd=cwd,
                path_suffix=path_suffix,
                abort=abort,
                test_subpath=test_subpath,
                )

        return path[:-(len(test_subpath) + 1)]

    def find_sessiondir(cwd=None, abort=False):
        """
        from:  my_project/my_session/some/subdir
        to:    my_project/my_session
        where: my_project/.bam/  (is the basedir)
        """
        session_rootdir = bam_config.find_basedir(
                cwd=cwd,
                test_subpath=bam_config.SESSION_FILE,
                abort=abort,
                descr="bam session"
                )

        if session_rootdir is not None:
            return session_rootdir[:-len(bam_config.SESSION_FILE)]
        else:
            if abort:
                if not os.path.isdir(session_rootdir):
                    fatal("Expected a directory (%r)" % session_rootdir)
            return None

    @staticmethod
    def load(id_="config", cwd=None, abort=False):
        filepath = bam_config.find_basedir(
                cwd=cwd,
                path_suffix=id_,
                descr="bam repository",
                )
        if abort is True:
            if filepath is None:
                fatal("Not a bam repository (or any of the parent directories): .bam")

        with open(filepath, 'r') as f:
            return json.load(f)

    @staticmethod
    def write(id_="config", data=None, cwd=None):
        filepath = bam_config.find_basedir(
                cwd=cwd,
                path_suffix=id_,
                descr="bam repository",
                )

        from bam.utils.system import write_json_to_file
        write_json_to_file(filepath, data)

    @staticmethod
    def write_bamignore(cwd=None):
        path = bam_config.find_rootdir(cwd=cwd)
        if path:
            filepath = os.path.join(path, ".bamignore")
            with open(filepath, 'w') as f:
                f.write(r".*\.blend\d+$")

    @staticmethod
    def create_bamignore_filter(id_=".bamignore", cwd=None):
        path = bam_config.find_rootdir()
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
               paths_uuid_update=None):

        paths_add = {}
        paths_remove = {}
        paths_modified = {}

        from bam.utils.system import uuid_from_file

        session_rootdir = os.path.abspath(session_rootdir)

        # don't commit metadata
        paths_used = {
            os.path.join(session_rootdir, ".bam_paths_uuid.json"),
            os.path.join(session_rootdir, ".bam_paths_remap.json"),
            os.path.join(session_rootdir, ".bam_deps_remap.json"),
            os.path.join(session_rootdir, ".bam_tmp.zip"),
            }

        paths_uuid = bam_session.load_paths_uuid(session_rootdir)

        for f_rel, sha1 in paths_uuid.items():
            f_abs = os.path.join(session_rootdir, f_rel)
            if os.path.exists(f_abs):
                sha1_modified = uuid_from_file(f_abs)
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

        for f_abs in iter_files(session_rootdir, bamignore_filter):
            if f_abs not in paths_used:
                # we should be clever - add the file to a useful location based on some rules
                # (category, filetype & tags?)

                f_rel = os.path.relpath(f_abs, session_rootdir)

                paths_add[f_rel] = f_abs

                if paths_uuid_update is not None:
                    paths_uuid_update[f_rel] = uuid_from_file(f_abs)

        return paths_add, paths_remove, paths_modified

    @staticmethod
    def load_paths_uuid(session_rootdir):
        with open(os.path.join(session_rootdir, ".bam_paths_uuid.json")) as f:
            return json.load(f)

    @staticmethod
    def is_dirty(session_rootdir):
        paths_add, paths_remove, paths_modified = bam_session.status(session_rootdir)
        return any((paths_add, paths_modified, paths_remove))


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

        # Create the default .bamignore
        # TODO (fsiddi) get this data from the project config on the server
        bam_config.write_bamignore(cwd=proj_dirname_abs)

        print("Project %r initialized" % proj_dirname)

    @staticmethod
    def create(session_name):
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
    def checkout(
            path,
            output_dir=None,
            session_rootdir_partial=None,
            all_deps=False,
            ):

        cfg = bam_config.load(abort=True)

        if output_dir is None:
            # fallback to the basename
            dst_dir = os.path.splitext(os.path.basename(path))[0]
        else:
            output_dir = os.path.realpath(output_dir)
            if os.sep in output_dir.rstrip(os.sep):
                # are we a subdirectory?
                # (we know this exists, since we have config already)
                project_rootdir = bam_config.find_rootdir(abort=True)
                if ".." in os.path.relpath(output_dir, project_rootdir).split(os.sep):
                    fatal("Output %r is outside the project path %r" % (output_dir, project_rootdir))
                del project_rootdir
            dst_dir = output_dir
        del output_dir

        if bam_config.find_sessiondir(cwd=dst_dir):
            fatal("Can't checkout in existing session. Use update.")

        payload = {
            "filepath": path,
            "command": "checkout",
            "arguments": json.dumps({
                "all_deps": all_deps,
                }),
            }

        import requests
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
    def update(paths):
        # Load project configuration
        # cfg = bam_config.load(abort=True)

        # TODO(cam) multiple paths
        session_rootdir = bam_config.find_sessiondir(paths[0], abort=True)
        # so as to avoid off-by-one errors string mangling
        session_rootdir = session_rootdir.rstrip(os.sep)

        paths_uuid = bam_session.load_paths_uuid(session_rootdir)

        if not paths_uuid:
            print("Nothing to update!")
            return

        if bam_session.is_dirty(session_rootdir):
            fatal("Local changes detected, commit before checking out!")

        # -------------------------------------------------------------------------------
        # TODO(cam) don't guess this important info
        files = [f for f in os.listdir(session_rootdir) if not f.startswith(".")]
        files_blend = [f for f in files if f.endswith(".blend")]
        if files_blend:
            f = files_blend[0]
        else:
            f = files[0]
        with open(os.path.join(session_rootdir, ".bam_paths_remap.json")) as fp:
            paths_remap = json.load(fp)
            paths_remap_relbase = paths_remap.get(".", "")
        path = os.path.join(paths_remap_relbase, f)
        # -------------------------------------------------------------------------------

        # merge sessions
        session_tmp = session_rootdir + ".tmp"
        bam_commands.checkout(
                path,
                output_dir=session_tmp,
                session_rootdir_partial=session_rootdir,
                )

        for dirpath, dirnames, filenames in os.walk(session_tmp):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                f_src = filepath
                f_dst = session_rootdir + filepath[len(session_tmp):]
                os.rename(f_src, f_dst)
        import shutil
        shutil.rmtree(session_tmp)

    @staticmethod
    def commit(paths, message):
        from bam.utils.system import write_json_to_file, write_json_to_zip
        import requests

        # Load project configuration
        cfg = bam_config.load(abort=True)

        session_rootdir = bam_config.find_sessiondir(paths[0], abort=True)

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
        paths_uuid = bam_session.load_paths_uuid(session_rootdir)

        # No longer used
        """
        with open(os.path.join(session_rootdir, ".bam_deps_remap.json")) as f:
            deps_remap = json.load(f)
        """

        paths_uuid_update = {}

        paths_add, paths_remove, paths_modified = bam_session.status(session_rootdir, paths_uuid_update)

        if not any((paths_add, paths_modified, paths_remove)):
            print("Nothing to commit!")
            return

        # we need to update paths_remap as we go
        with open(os.path.join(session_rootdir, ".bam_paths_remap.json")) as f:
            paths_remap = json.load(f)
            paths_remap_relbase = paths_remap.get(".", "")

        def remap_filepath(f_rel):
            f_rel_in_proj = paths_remap.get(f_rel)
            if f_rel_in_proj is None:
                if paths_remap_relbase:
                    if f_rel.startswith("_"):
                        f_rel_in_proj = f_rel[1:]
                    else:
                        f_rel_in_proj = os.path.join(paths_remap_relbase, f_rel)
                else:
                    if f_rel.startswith("_"):
                        # we're already project relative
                        f_rel_in_proj = f_rel[1:]
                    else:
                        f_rel_in_proj = f_rel

            return f_rel_in_proj

        def remap_cb(f, data):
            # check for the absolute path hint
            if f.startswith(b'//_'):
                proj_base_b = data
                return b'//' + os.path.relpath(f[3:], proj_base_b)
            return None

        def remap_file(f_rel, f_abs):
            f_abs_remap = os.path.join(basedir_temp, f_rel)
            dir_remap = os.path.dirname(f_abs_remap)
            os.makedirs(dir_remap, exist_ok=True)

            # final location in the project
            f_rel_in_proj = remap_filepath(f_rel)
            proj_base_b = os.path.dirname(f_rel_in_proj).encode("utf-8")

            from bam.blend import blendfile_pack_restore
            blendfile_pack_restore.blendfile_remap(
                    f_abs.encode('utf-8'),
                    dir_remap.encode('utf-8'),
                    deps_remap_cb=remap_cb,
                    deps_remap_cb_userdata=proj_base_b,
                    )
            return f_abs_remap

        for f_rel, f_abs in list(paths_modified.items()):
            if f_abs.endswith(".blend"):
                f_abs_remap = remap_file(f_rel, f_abs)
                if os.path.exists(f_abs_remap):
                    paths_modified[f_rel] = f_abs_remap

        for f_rel, f_abs in list(paths_add.items()):
            if f_abs.endswith(".blend"):
                f_abs_remap = remap_file(f_rel, f_abs)
                if os.path.exists(f_abs_remap):
                    paths_add[f_rel] = f_abs_remap

        """
                deps = deps_remap.get(f_rel)
                if deps:
                    # ----
                    # remap!
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
        """

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

            paths_remap_subset = {
                    f_rel: f_rel_in_proj
                    for f_rel, f_rel_in_proj in paths_remap.items() if f_rel in paths_modified}
            paths_remap_subset.update({
                    f_rel: remap_filepath(f_rel)
                    for f_rel in paths_add})

            # paths_remap_subset.update(paths_remap_subset_add)
            write_json_to_zip(zip_handle, ".bam_paths_remap.json", paths_remap_subset)

            # build a list of path manipulation operations
            paths_ops = {}
            # paths_remove ...
            for f_rel, f_abs in paths_remove.items():
                # TODO
                f_abs_remote = paths_remap[f_rel]
                paths_ops[f_abs_remote] = 'D'

            write_json_to_zip(zip_handle, ".bam_paths_ops.json", paths_ops)
            log.debug(paths_ops)

        if os.path.exists(basedir_temp):
            import shutil
            shutil.rmtree(basedir_temp)
            del shutil

        # --------------
        # Commit Request
        payload = {
            "command": "commit",
            "arguments": json.dumps({
                'message': message,
                }),
            }
        files = {
            "file": open(temp_zip, 'rb'),
            }

        r = requests.put(
                bam_session.request_url("file"),
                params=payload,
                auth=(cfg["user"], cfg["password"]),
                files=files)

        files["file"].close()
        os.remove(temp_zip)

        try:
            r_json = r.json()
            print(r_json.get("message", "<empty>"))
        except Exception:
            print(r.text)

        # TODO, handle error cases
        ok = True
        if ok:

            # ----------
            # paths_uuid
            paths_uuid.update(paths_uuid_update)
            write_json_to_file(os.path.join(session_rootdir, ".bam_paths_uuid.json"), paths_uuid_update)

            # -----------
            # paths_remap
            paths_remap.update(paths_remap_subset)
            for k in paths_remove:
                del paths_remap[k]
            write_json_to_file(os.path.join(session_rootdir, ".bam_paths_remap.json"), paths_remap)
            del write_json_to_file

    @staticmethod
    def status(paths, use_json=False):
        # TODO(cam) multiple paths
        path = paths[0]
        del paths

        session_rootdir = bam_config.find_sessiondir(path, abort=True)
        paths_add, paths_remove, paths_modified = bam_session.status(session_rootdir)

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

        def deps_path_walker():
            from bam.blend import blendfile_path_walker
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

    @staticmethod
    def pack(
            paths,
            output,
            all_deps=False,
            use_quiet=False,
            compress_level=-1,
            ):
        # Local packing (don't use any project/session stuff)
        from .blend import blendfile_pack

        # TODO(cam) multiple paths
        path = paths[0]
        del paths

        if use_quiet:
            report = lambda msg: None
        else:
            report = lambda msg: print(msg, end="")

        for msg in blendfile_pack.pack(
                path.encode('utf-8'),
                output.encode('utf-8'),
                'ZIP',
                all_deps=all_deps,
                compress_level=compress_level,
                report=report,
                ):
            pass

    @staticmethod
    def remap_start(
            paths,
            use_json=False,
            ):
        filepath_remap = "bam_remap.data"

        for p in paths:
            if not os.path.exists(p):
                fatal("Path %r not found!" % p)
        paths = [p.encode('utf-8') for p in paths]


        if os.path.exists(filepath_remap):
            fatal("Remap in progress, run with 'finish' or remove %r" % filepath_remap)

        from bam.blend import blendfile_path_remap
        remap_data = blendfile_path_remap.start(
                paths,
                use_json=use_json,
                )

        with open(filepath_remap, 'wb') as fh:
            import pickle
            pickle.dump(remap_data, fh, pickle.HIGHEST_PROTOCOL)

    @staticmethod
    def remap_finish(
            paths,
            force_relative=False,
            dry_run=False,
            use_json=False,
            ):
        filepath_remap = "bam_remap.data"

        for p in paths:
            if not os.path.exists(p):
                fatal("Path %r not found!" % p)
        # bytes needed for blendfile_path_remap API
        paths = [p.encode('utf-8') for p in paths]

        if not os.path.exists(filepath_remap):
            fatal("Remap not started, run with 'start', (%r not found)" % filepath_remap)

        with open(filepath_remap, 'rb') as fh:
            import pickle
            remap_data = pickle.load(fh)

        from bam.blend import blendfile_path_remap
        blendfile_path_remap.finish(
                paths, remap_data,
                force_relative=force_relative,
                dry_run=dry_run,
                use_json=use_json,
                )

        if not dry_run:
            os.remove(filepath_remap)

    @staticmethod
    def remap_reset(
            use_json=False,
            ):
        filepath_remap = "bam_remap.data"
        if os.path.exists(filepath_remap):
            os.remove(filepath_remap)
        else:
            fatal("remapping not started, nothing to do!")


# -----------------------------------------------------------------------------
# Argument Parser

def init_argparse_common(
        subparse,
        use_json=False,
        use_all_deps=False,
        use_quiet=False,
        use_compress_level=False,
        ):
    import argparse

    if use_json:
        subparse.add_argument(
                "-j", "--json", dest="json", action='store_true',
                help="Generate JSON output",
                )
    if use_all_deps:
        subparse.add_argument(
                "-a", "--all-deps", dest="all_deps", action='store_true',
                help="Follow all dependencies (unused indirect dependencies too)",
                )
    if use_quiet:
        subparse.add_argument(
                "-q", "--quiet", dest="use_quiet", action='store_true',
                help="Suppress status output",
                )
    if use_compress_level:
        class ChoiceToZlibLevel(argparse.Action):
            def __call__(self, parser, namespace, value, option_string=None):
                setattr(namespace, self.dest, {"default": -1, "fast": 1, "best": 9, "store": 0}[value[0]])

        subparse.add_argument(
                "-c", "--compress", dest="compress_level", nargs=1, default=-1, metavar='LEVEL',
                action=ChoiceToZlibLevel,
                choices=('default', 'fast', 'best', 'store'),
                help="Compression level for resulting archive",
                )


def create_argparse_init(subparsers):
    subparse = subparsers.add_parser("init",
            help="Initialize a new project directory")
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
            help="Checkout a remote path in an existing project",
            )
    subparse.add_argument(
            dest="path", type=str, metavar='REMOTE_PATH',
            help="Path to checkout on the server",
            )
    subparse.add_argument(
            "-o", "--output", dest="output", type=str, metavar='DIRNAME',
            help="Local name to checkout the session into (optional, falls back to path name)",
            )

    init_argparse_common(subparse, use_all_deps=True)

    subparse.set_defaults(
            func=lambda args:
            bam_commands.checkout(args.path, args.output, args.all_deps),
            )


def create_argparse_update(subparsers):
    subparse = subparsers.add_parser(
            "update", aliases=("up",),
            help="Update a local session with changes from the remote project",
            )
    subparse.add_argument(
            dest="paths", nargs="*",
            help="Path(s) to operate on",
            )
    subparse.set_defaults(
            func=lambda args:
            bam_commands.update(args.paths or ["."]),
            )


def create_argparse_commit(subparsers):
    subparse = subparsers.add_parser(
            "commit", aliases=("ci",),
            help="Commit changes from a session to the remote project",
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


def create_argparse_revert(subparsers):
    subparse = subparsers.add_parser(
            "revert", aliases=("rv",),
            help="Reset local changes back to the state at time of checkout",
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
            help="Show any edits made in the local session",
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
            help="List the contents of a remote directory",
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
                    use_json=args.json,
                    ),
                    )


def create_argparse_deps(subparsers):
    subparse = subparsers.add_parser(
            "deps", aliases=("dp",),
            help="List dependencies for file(s)",
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


def create_argparse_pack(subparsers):
    subparse = subparsers.add_parser(
            "pack", aliases=("pk",),
            help="Pack a blend file and its dependencies into an archive",
            )
    subparse.add_argument(
            dest="paths", nargs="+",
            help="Path(s) to operate on",
            )
    subparse.add_argument(
            "-o", "--output", dest="output", metavar='ZIP', required=True,
            help="Output file or a directory when multiple inputs are passed",
            )

    init_argparse_common(subparse, use_all_deps=True, use_quiet=True, use_compress_level=True)

    subparse.set_defaults(
            func=lambda args:
            bam_commands.pack(
                    args.paths,
                    args.output,
                    all_deps=args.all_deps,
                    use_quiet=args.use_quiet,
                    compress_level=args.compress_level),
                    )


def create_argparse_remap(subparsers):
    subparse = subparsers.add_parser(
            "remap",
            help="Remap blend file paths",
            )

    subparse_remap_commands = subparse.add_subparsers(
            title="Remap commands",
            description='valid subcommands',
            help='additional help',
            )
    sub_subparse = subparse_remap_commands.add_parser(
            "start",
            help="Start remapping the blend files",
            )

    sub_subparse.add_argument(
            dest="paths", nargs="*",
            help="Path(s) to operate on",
            )
    init_argparse_common(sub_subparse, use_json=True)

    sub_subparse.set_defaults(
            func=lambda args:
            bam_commands.remap_start(
                    args.paths or ["."],
                    use_json=args.json,
                    ),
                    )

    sub_subparse = subparse_remap_commands.add_parser(
            "finish",
            help="Finish remapping the blend files",
            )
    sub_subparse.add_argument(
            dest="paths", nargs="*",
            help="Path(s) to operate on",
            )
    sub_subparse.add_argument(
            "-r", "--force-relative", dest="force_relative", action='store_true',
            help="Make all remapped paths relative (even if they were originally absolute)",
            )
    sub_subparse.add_argument(
            "-d", "--dry-run", dest="dry_run", action='store_true',
            help="Just print output as if the paths are being run",
            )
    init_argparse_common(sub_subparse, use_json=True)

    sub_subparse.set_defaults(
            func=lambda args:
            bam_commands.remap_finish(
                    args.paths or ["."],
                    force_relative=args.force_relative,
                    dry_run=args.dry_run,
                    use_json=args.json,
                    ),
                    )

    sub_subparse = subparse_remap_commands.add_parser(
            "reset",
            help="Cancel path remapping",
            )
    init_argparse_common(sub_subparse, use_json=True)

    sub_subparse.set_defaults(
            func=lambda args:
            bam_commands.remap_reset(
                    use_json=args.json,
                    ),
            )


def create_argparse():
    import argparse

    usage_text = (
        "BAM!\n" +
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
    create_argparse_pack(subparsers)
    create_argparse_remap(subparsers)

    return parser


def main(argv=None):
    if argv is None:
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
