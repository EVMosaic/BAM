
class FilePath:
    """
    Tiny filepath class to hide blendfile.
    """
    __slots__ = (
        "block",
        "path",

        # only for convenience
        "basepath",
        )

    def __init__(self, block, path, basepath):
        self.block = block
        self.path = path

        # a bit of overhead, but handy
        self.basepath = basepath

    # --------
    # filepath
    #
    @property
    def filepath(self):
        return self.block[self.path]

    @filepath.setter
    def filepath(self, filepath):
        self.block[self.path] = filepath

    # ------------------------------------------------------------------------
    # Main function to visit paths

    @staticmethod
    def visit_from_blend(filepath, access="rb", recursive=False):
        import os

        basedir = os.path.dirname(os.path.abspath(filepath))

        import blendfile
        blend = blendfile.open_blend(filepath, access)

        for block in blend.find_blocks_from_code(b'IM'):
            yield FilePath(block, b'name', basedir)

        for block in blend.find_blocks_from_code(b'LI'):
            yield FilePath(block, b'name', basedir)

        for block in blend.find_blocks_from_code(b'ID'):
            lib_id = block[b"lib"]
            lib = blend.find_block_from_offset(lib_id)
            # print(block.fields)
            print(block)
            print(lib)
            # import IPython; IPython.embed()

        blend.close()


class utils:
    # fake module
    __slots__ = ()

    @staticmethod
    def abspath(path, start=None, library=None):
        import os
        if path.startswith(b"//"):
            # if library:
            #     start = os.path.dirname(abspath(library.filepath))
            return os.path.join(start, path[2:])
        return path


def pack(blendfile_src, blendfile_dst):
    import os
    import shutil

    dst_blend_tmp = blendfile_src + b"@"
    shutil.copy(blendfile_src, dst_blend_tmp)
    path_copy_ls = []

    base_dir_src = os.path.dirname(blendfile_src)
    base_dir_dst = os.path.dirname(blendfile_dst)

    for fp in FilePath.visit_from_blend(dst_blend_tmp, access="r+b"):
        # assume the path might be relative
        path_rel = fp.filepath
        path_base = path_rel.split(b"\\")[-1].split(b"/")[-1]
        path_src = utils.abspath(path_rel, base_dir_src)
        path_dst = os.path.join(base_dir_dst, path_base)

        # rename in the blend
        fp.filepath = b"//" + path_base

        # add to copylist
        path_copy_ls.append((path_src, path_dst))

    shutil.move(dst_blend_tmp, blendfile_dst)

    for src, dst in path_copy_ls:
        if not os.path.exists(src):
            print("  Source missing! %r" % src)
        else:
            print("  Copying %r -> %r" % (src, dst))
            shutil.copy(src, dst)

    print("  Written:", blendfile_dst)


if __name__ == "__main__":
    pack(b"/d/test/paths.blend", b"/d/test/out/paths.blend")
