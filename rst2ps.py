
# -----
# blender -P rst2ps.py

def ps_from_obj(fw, obj, global_matrix):
    matrix = global_matrix * obj.matrix_world
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


def ps_write(fw):
    fw("%!PS\n")
    fw("%%Creator: rst2ps.py\n")
    fw("%%CreationDate: 17 October 2003\n")
    fw("%%Title: BlahBlah\n")
    fw("%%BoundingBox: 0 0 1000 700\n")
    fw("%%DocumentMedia: a4 0 0 1000 700 () ()\n")
    fw("%%Pages: 1\n")
    fw("%%EndComments\n")
    fw("0 0 translate\n")

    import mathutils

    global_scale = 100.0
    global_matrix = mathutils.Matrix.Scale(global_scale, 4)

    import bpy
    scene = bpy.context.scene
    for obj in scene.objects:
        if obj.type == 'CURVE':
            ps_from_obj(fw, obj, global_matrix)

    fw("showpage\n")

f = open("/test.ps", "w")
ps_write(f.write)
f.close()
