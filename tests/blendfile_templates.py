# Apache License, Version 2.0

# Pass in:
#
#    blender --python blendfile_templates.py -- destination/file.blend create_command return_code
#
# 'return_code' can be any number, use to check the script completes.


def _clear_blend():
    import bpy

    # copied from batch_import.py
    unique_obs = set()
    for scene in bpy.data.scenes:
        for obj in scene.objects[:]:
            scene.objects.unlink(obj)
            unique_obs.add(obj)

    # remove obdata, for now only worry about the startup scene
    for bpy_data_iter in (bpy.data.objects, bpy.data.meshes, bpy.data.lamps, bpy.data.cameras):
        for id_data in bpy_data_iter:
            bpy_data_iter.remove(id_data)


def create_blank(blendfile_root, _create_data, deps):
    assert(isinstance(deps, list))


def create_image_single(blendfile_root, _create_data, deps):
    import bpy

    path = "//my_image.png"
    image = bpy.data.images.new(name="MyImage", width=512, height=512)
    image.filepath_raw = path
    deps.append(bpy.path.abspath(path))
    image.file_format = 'PNG'
    image.use_fake_user = True
    image.save()


def create_from_files(blendfile_root, _create_data, deps):
    """Create a blend file which users all sub-directories.
    (currently images only)
    """
    import os
    import bpy

    def iter_files_blend(path):
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                yield filepath

    # dirname = os.path.dirname(bpy.data.filepath)
    dirname = blendfile_root
    for f_abs in iter_files_blend(dirname):
        if f_abs.endswith(".png"):
            f_rel = bpy.path.relpath(f_abs)
            image = bpy.data.images.load(f_rel)
            image.use_fake_user = True
            deps.append(f_abs)


def create_from_file_liblinks(blendfile_root, create_data, deps):
    # _clear_blend()
    # create_data is a list of string pairs:
    # [(blend_file, data_id, links_to)]
    import os
    import bpy

    def savefile(f):
        bpy.ops.wm.save_mainfile('EXEC_DEFAULT', filepath=f)

    def newfile(f):
        bpy.ops.wm.read_factory_settings()
        _clear_blend()
        savefile(f)

    # NOTE: no attempt has been made to optimize loop below
    # we rely on this being < 10 items to not be completely slow!
    print(create_data)
    data_id_map = {f: f_id for (f, f_id, f_link) in create_data}
    done = {bpy.data.filepath}

    # simplifies logic below
    os.remove(bpy.data.filepath)

    ok = True
    while ok:
        ok = False
        for f, f_id, f_links in create_data:
            if not os.path.exists(f):
                print(f_links)
                if not f_links or all(os.path.exists(l) for l in f_links):
                    if f != bpy.data.filepath:
                        newfile(f)

                    scene = bpy.context.scene

                    # we have a path with an existing link!
                    ok = True
                    for i, l_abs in enumerate(f_links):
                        l_rel = bpy.path.relpath(l_abs)
                        with bpy.data.libraries.load(l_rel, link=True) as (data_src, data_dst):
                            data_dst.scenes = [data_id_map[l_abs]]

                        scene_link = bpy.data.scenes[data_id_map[l_abs]]
                        edit = scene.sequence_editor_create()
                        edit.sequences.new_scene(
                                name=scene_link.name,
                                scene=scene_link,
                                frame_start=1,
                                channel=i,
                                )

                    # save the file with a new scene name
                    scene.name = f_id
                    bpy.ops.wm.save_mainfile('EXEC_DEFAULT', filepath=f)
                    done.add(f)

    if len(create_data) != len(done):
        raise Exception(
                "Paths could not be resolved (cyclic deps) %r!" %
                tuple(sorted({f for f, f_id, f_links in create_data} - done)))


if __name__ == "__main__":
    import sys
    blendfile, blendfile_root, blendfile_deps_json, create_id, create_data, returncode = sys.argv[-6:]
    returncode = int(returncode)
    create_fn = globals()[create_id]

    if create_data != "NONE":
        with open(create_data, 'r') as f:
            import json
            create_data = json.load(f)
            del json

    # ----
    import bpy
    # no need for blend1's
    bpy.context.user_preferences.filepaths.save_version = 0
    # WEAK! (but needed)
    # save the file first, so we can do real, relative dirs
    bpy.ops.wm.save_mainfile('EXEC_DEFAULT', filepath=blendfile)
    del bpy
    # ----

    _clear_blend()
    deps = []

    create_fn(blendfile_root, create_data, deps)

    if deps:
        with open(blendfile_deps_json, 'w') as f:
            import json
            json.dump(
                    deps, f, ensure_ascii=False,
                    check_circular=False,
                    # optional (pretty)
                    sort_keys=True, indent=4, separators=(',', ': '),
                    )
            del json

    import bpy
    bpy.ops.wm.save_mainfile('EXEC_DEFAULT', filepath=blendfile)

    import sys
    sys.exit(returncode)
