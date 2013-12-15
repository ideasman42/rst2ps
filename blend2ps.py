# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####
#
# Copyright Campbell Barton

# ----------------------------------------------------------------------------
# Postscript writing functions


def ps_from_poly(fw, points, color=(0.0, 0.0, 0.0)):
    fw("newpath\n")
    for i, p in enumerate(points):
        fw("%.6f %.6f %s\n" % (p[0], p[1], "moveto" if i == 0 else "lineto"))
    fw("closepath\n")
    fw("%.4f %.4f %.4f setrgbcolor\n" % color)
    fw("fill\n")


def ps_from_obj_curve(fw, obj, matrix):

    def spline_segments_bezier(spline):
        points = spline.bezier_points[:]

        if spline.use_cyclic_u:
            p_prev = points[-1]
        else:
            points.append(points.pop(0))
            p_prev = points[-1]
            points.pop()

        for p in points:
            yield (
                matrix * p_prev.co,
                matrix * p_prev.handle_right,
                matrix * p.handle_left,
                matrix * p.co)
            p_prev = p

    def ps_from_material(material):
        if material is not None:
            rgb = material.diffuse_color[:]
        else:
            rgb = 0.0, 0.0, 0.0
        fw("%.4f %.4f %.4f setrgbcolor\n" % rgb)

    fw("newpath\n")

    cu = obj.data
    is_fill_ok = (cu.fill_mode != 'NONE') and (cu.dimensions != '3D')

    if not is_fill_ok:
        fw("%.6f setlinewidth\n" % ((2.0 * cu.bevel_depth) * matrix.median_scale))

    for is_fill in ((False, True) if is_fill_ok else (False,)):
        for material_index, material in enumerate(cu.materials if cu.materials else (None,)):
            for spline in cu.splines:
                if spline.material_index == material_index:

                    if is_fill_ok and (spline.use_cyclic_u != is_fill):
                        continue

                    if spline.type == 'POLY':
                        for i, p in enumerate(spline.points):
                            p = matrix * p.co.xyz
                            fw("%.6f %.6f %s\n" % (p[0], p[1], "moveto" if i == 0 else "lineto"))
                        if spline.use_cyclic_u:
                            fw("closepath\n")

                    elif spline.type == 'BEZIER':
                        i = 0
                        for pa, pah, pbh, pb in spline_segments_bezier(spline):
                            if i == 0:
                                fw("%.6f %.6f moveto\n" % pa[:2])
                            fw("%.6f %.6f %.6f %.6f %.6f %.6f curveto\n" % (pah[:2] + pbh[:2] + pb[:2]))
                            i += 1
                        if spline.use_cyclic_u:
                            fw("closepath\n")

            ps_from_material(material)

            if is_fill:
                fw("fill\n")
            else:
                fw("stroke\n")


def ps_from_obj_image(fw, obj, matrix, no_image=False):
    # Seems this is ghostscript specific
    # requires '-dNOSAFER' arg.
    import bpy
    import os

    image = obj.data

    if image is None:
        return

    is_missing = False

    filepath = bpy.path.abspath(image.filepath, library=image.library)
    filepath = os.path.normpath(filepath)

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

    if no_image:
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

# ----------------------------------------------------------------------------
# Write Functions (exposed externally)


def ps_write(fw,
             no_image=False):

    # first calculate the view matrix and boundbox using an ortho camera.

    import bpy
    import os

    scene = bpy.context.scene

    global_matrix, bounds = ps_header_viewbounds(scene)

    fw("%!PS\n")
    fw("%%Creator: rst2ps.py\n")
    fw("%%CreationDate: " + ("%s\n" % ps_header_datestring()))
    fw("%%Title: " + ("%s\n" % os.path.basename(bpy.data.filepath)))
    fw("%%BoundingBox: " + ("0 0 %.6f %.6f\n" % (bounds[0], bounds[1])))
    # fw("%%DocumentMedia: a4 0 0 1000 700 () ()\n")
    #fw("%%Pages: 1\n")
    fw("%%EndComments\n")

    # Blender camera coords use (x0, y0) is the middle of the page.
    # for the postscript file, use (x0, y0) as bottom left
    # makes choosing page size easier in ghostview.
    fw("%.6f %.6f translate\n" % (bounds[0] / 2.0, bounds[1] / 2.0))

    objects = list(ps_scene_objects(scene, global_matrix))
    # sort by depth then object name
    objects.sort(key=lambda item: (item[1][2][3], item[0].name))

    for obj, matrix in objects:
        if obj.type in {'CURVE', 'FONT'}:
            ps_from_obj_curve(fw, obj, matrix)
        elif obj.type == 'EMPTY':
            ps_from_obj_image(fw, obj, matrix,
                              no_image=no_image)

    fw("showpage\n")


def write(filepath,
          no_image=False,
          ):
    with open(filepath, 'w') as file:
        ps_write(file.write,
                 no_image=no_image)


# ----------------------------------------------------------------------------
# Command line access

def main():
    import sys
    import argparse

    # Runs inside blender, use args after '--'
    argv = sys.argv
    if "--" not in argv:
        argv = []  # as if no args are passed
    else:
        argv = argv[argv.index("--") + 1:]  # get all args after "--"

    # When --help or no args are given, print this help
    usage_text = (
        "Write out a postscript (.ps / .pdf) document for this blend file:"
        "  blender --background --python " + __file__ + " -- [options]\n"
        )

    parser = argparse.ArgumentParser(description=usage_text)

    parser.add_argument("-o", "--output", dest="output_path", metavar='FILE',
                        help="Save the generated file to the specified path")

    parser.add_argument('-n', '--no_image', dest="no_image", default=False, action="store_true",
                        help="Use placeholders for images")

    args = parser.parse_args(argv)  # In this example we wont use the args

    if not argv:
        parser.print_help()
        return

    write(args.output_path,
          no_image=args.no_image,
          )

if __name__ == "__main__":
    main()
