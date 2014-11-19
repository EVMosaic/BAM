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


def create_blank():
    pass


def create_image_single():
    import bpy
    image = bpy.data.images.new(name="MyImage", width=512, height=512)
    image.filepath_raw = "//my_image.png"
    image.file_format = 'PNG'
    image.use_fake_user = True
    image.save()


if __name__ == "__main__":
    import sys
    blendfile, create_id, returncode = sys.argv[-3:]
    returncode = int(returncode)
    create_fn = globals()[create_id]

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
    create_fn()

    import bpy
    bpy.ops.wm.save_mainfile('EXEC_DEFAULT', filepath=blendfile)

    import sys
    sys.exit(returncode)

