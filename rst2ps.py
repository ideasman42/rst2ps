
# -----
# blender -P rst2ps.py
# ps2pdf -dEPSCrop -dAutoRotatePages=/None -dAutoFilterColorImages=false -dColorImageFilter=/FlateEncode -dUseFlateCompression=true /test.ps
# /src/rst2ps/tests/camera.blend
#
#
# b -b /src/rst2ps/tests/camera.blend --python /src/rst2ps/rst2ps.py

def ps_from_poly(fw, points, color=(0.0, 0.0, 0.0)):
    fw("newpath\n")
    for i, p in enumerate(points):
        fw("%.6f %.6f %s\n" % (p[0], p[1], "moveto" if i == 0 else "lineto"))
    fw("closepath\n")
    fw("%.4f %.4f %.4f setrgbcolor\n" % color)
    fw("fill\n")


def ps_from_obj_curve(fw, obj, matrix):
    def spline_segments(spline):
        points = spline.bezier_points[:]
        p_prev = points[-1]
        for p in points:
            yield (
                matrix * p_prev.co,
                matrix * p_prev.handle_right,
                matrix * p.handle_left,
                matrix * p.co)
            p_prev = p

    cu = obj.data

    for material_index, material in enumerate(cu.materials if cu.materials else (None,)):
        for spline in cu.splines:
            if not spline.bezier_points:
                continue  # TODO
            if spline.material_index == material_index:
                i = 0
                for pa, pah, pbh, pb in spline_segments(spline):
                    if i == 0:
                        fw("%.6f %.6f moveto\n" % pa[:2])
                    fw("%.6f %.6f %.6f %.6f %.6f %.6f curveto\n" % (pah[:2] + pbh[:2] + pb[:2]))
                    i += 1

                fw("closepath\n")

        if material is not None:
            rgb = material.diffuse_color[:]
        else:
            rgb = 0.0, 0.0, 0.0
        fw("%.4f %.4f %.4f setrgbcolor\n" % rgb)

        fw("fill\n")


def ps_from_obj_image(fw, obj, matrix, use_placeholder=False):
    # Seems this is ghostscript specific
    # requires '-dNOSAFER' arg.
    import bpy
    import os

    image = obj.data

    if image is None:
        return

    is_missing = False

    filepath = bpy.path.abspath(image.filepath, library=image.library)

    if not os.path.exists(filepath):
        print("  image path missing: %r -> %r" % (obj.name, filepath))
        is_missing = True

    x, y = image.size
    x = max(1, x)
    y = max(1, y)

    if x < y:
        aspx, aspy = x / y, 1.0
    else:
        aspx, aspy = 1.0, y / x


    from math import degrees
    from mathutils import Vector

    points = [Vector() for i in range(4)]
    dim = obj.empty_draw_size
    ofs = [f * dim for f in obj.empty_image_offset]

    points[0].xy = 0.0, 0.0
    points[1].xy = 0.0, dim
    points[2].xy = dim, dim
    points[3].xy = dim, 0.0

    for p in points:
        p.x = (p.x + ofs[0]) * aspx
        p.y = (p.y + ofs[1]) * aspy

    points = [matrix * p for p in points]

    if use_placeholder:
        ps_from_poly(fw, points, color=(0.0, 0.0, 0.0))
    elif is_missing:
        ps_from_poly(fw, points, color=(1.0, 0.0, 1.0))
    else:
        # place image based on 'points' quad vectors.
        fw("gsave\n")

        fw("%.6f %.6f translate\n" % (points[1][0], points[1][1]))
        fw("%.6f rotate\n" % degrees((points[0] - points[1]).xy.angle_signed(Vector((0.0, -1.0)))))

        dim_x = (points[0].xy - points[3].xy).length
        dim_y = (points[0].xy - points[1].xy).length

        mtx_x = x / dim_x
        mtx_y = y / dim_y

        fw("%d %d "  # size of image
           "8 "  # bits per channel (1, 2, 4, or 8)
           "[%.6f 0 0 %.6f 0 %.6f] "  # transform array... maps unit square to pixel
           "(%s) (r) file/DCTDecode filter "  # opens the file and filters the image data
           "false "  # _don't_ pull channels from separate sources.
           "3 "  # channels
           "colorimage\n" % (x, y,
                             mtx_x, -mtx_y, mtx_y,  # matrix values
                             filepath))
        fw("grestore\n")


def ps_header_datestring():
    import datetime
    now = datetime.datetime.now()
    # eg: "14 December 2013"
    return now.strftime("%d %B %Y")


def ps_header_viewbounds(scene):
    import mathutils
    # return: (w, h), matrix
    global_scale = 100.0
    cam_ob = scene.camera
    matrix = cam_ob.matrix_world.copy()
    ortho_scale = cam_ob.data.ortho_scale
    x = float(scene.render.resolution_x)
    y = float(scene.render.resolution_y)
    if x < y:
        aspx, aspy = x / y, 1.0
    else:
        aspx, aspy = 1.0, y / x

    global_matrix = mathutils.Matrix.Scale(global_scale, 4) * matrix.inverted()

    return global_matrix, (global_scale * ortho_scale * aspx,
                           global_scale * ortho_scale * aspy)


def ps_scene_objects(scene, global_matrix):
    for obj_main in scene.objects:

        # dupli-parent?
        parent = obj_main.parent
        if (parent is not None) and (parent.dupli_type in {'VERTS', 'FACES'}):
            continue

        if obj_main.dupli_type != 'NONE':
            obj_main.dupli_list_create(scene)

            for dob in obj_main.dupli_list:
                yield (dob.object, global_matrix * dob.matrix)

            obj_main.dupli_list_clear()

        yield (obj_main, global_matrix * obj_main.matrix_world)

    scene_set = scene.background_set
    if scene_set is not None:
        yield from ps_scene_objects(scene_set, global_matrix)


def ps_write(fw):

    # first calculate the view matrix and boundbox using an ortho camera.

    import bpy
    import os

    scene = bpy.context.scene

    global_matrix, bounds = ps_header_viewbounds(scene)
    global_scale = 1.0

    fw("%!PS\n")
    fw("%%Creator: rst2ps.py\n")
    fw("%%CreationDate: " + ("%s\n" % ps_header_datestring()))
    fw("%%Title: " + ("%s\n" % os.path.basename(bpy.data.filepath)))
    fw("%%BoundingBox: " + ("%.6f %.6f %.6f %.6f\n" %
            (bounds[0] / -2, bounds[1] / -2, bounds[0] / 2, bounds[1] / 2)))
    # fw("%%DocumentMedia: a4 0 0 1000 700 () ()\n")
    fw("%%Pages: 1\n")
    fw("%%EndComments\n")
    fw("0 0 translate\n")

    import mathutils

    objects = list(ps_scene_objects(scene, global_matrix))
    # sort by depth then object name
    objects.sort(key=lambda item: (item[1][2][3], item[0].name))

    for obj, matrix in objects:
        if obj.type in {'CURVE', 'FONT'}:
            ps_from_obj_curve(fw, obj, matrix)
        elif obj.type == 'EMPTY':
            ps_from_obj_image(fw, obj, matrix)

    fw("showpage\n")


f = open("/test.ps", "w")
ps_write(f.write)
f.close()

# import os
# -dNOSAFER for images
# os.system("ps2pdf -dNOSAFER -dEPSCrop -dAutoRotatePages=/None -dAutoFilterColorImages=false -dColorImageFilter=/FlateEncode -dUseFlateCompression=true /test.ps /test.pdf")
# gv  -nosafer /test.ps
#
# b -b /src/rst2ps/tests/camera.blend --python /src/rst2ps/rst2ps.py ; gv -nosafer /test.ps
