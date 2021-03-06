import docutils.parsers.rst

def rst2tree(txt):
    import docutils.parsers.rst
    parser = docutils.parsers.rst.Parser()
    document = docutils.utils.new_document("test")
    document.settings.tab_width = 4
    document.settings.pep_references = False
    document.settings.rfc_references = False

    document.settings.raw_enabled = True  # TODO, check how this works!
    document.settings.file_insertion_enabled = True

    parser.parse(txt, document)
    return document

if 0:
    doc = rst2tree(open("/src/the_joy_of_life_drawing/book.rst", 'r', encoding="utf-8").read())
elif 0:
    doc = rst2tree(open("/src/pyfbx_i42/fbx_spec.rst", 'r').read())
else:
    _text = """

This is a title
===============

Hello this is some text para 1.

- Point one.

- Point two.

- Foo fa fa.

  Some sub text.

  - Some sub list.

  - Some subsub.


Lets try enum list.

#. Hello.

#. Another.


Character list.

A) List item.

A) another.

A) and another.

Subtitle
--------

.. class:: center

   Sorry to say but here is some more.

Lets *also* include some **basic** formatting.

The End.
"""
    doc = rst2tree(_text)
    del _text


# ------------------------------------------------------------------------------
# Handle all blender conversion here

def butil_text_add_default(scene, style):
    import bpy

    txt_cu = bpy.data.curves.new(name="MyText", type='FONT')
    txt_cu.fill_mode = 'NONE'
    txt_cu.resolution_u = 2
    txt_cu.offset_y = -1.0  # useful so we can place from top down.

    if style is not None:
        txt_cu.size = style.size
        if style.font is not None:
            txt_cu.font = style.font
        if style.font_bold is not None:
            txt_cu.font_bold = style.font_bold
        if style.font_italic is not None:
            txt_cu.font_italic = style.font_italic

    txt_ob = bpy.data.objects.new(name="MyText", object_data=txt_cu)
    scene.objects.link(txt_ob)
    return txt_ob, txt_cu


def butil_text_set_body(txt_cu, body, body_fmt):
    assert(len(body) == len(body_fmt))

    txt_cu.body = body

    bfmt_array = txt_cu.body_format
    for i, fmt in enumerate(body_fmt):
        if fmt & 1:
            bfmt_array[i].use_bold = True
        if fmt & 2:
            bfmt_array[i].use_italic = True

def butil_text_calc_advance(scene, txt_ob):
    txt_ob.update_tag()
    scene.update()

    # we could be clever and find real number of lines
    advance = txt_ob.bound_box[0][1] + txt_ob.location.y
    print(advance)

    return advance

def butil_text_to_blend(conf, indent, style, body, body_fmt, align):

    txt_ob, txt_cu = butil_text_add_default(conf.scene, style)

    indent_dist = style.size * indent * 1.6
    box = txt_cu.text_boxes[0]
    box.x = indent_dist
    box.width = conf.page_width - indent_dist

    butil_text_set_body(txt_cu, body, body_fmt)

    txt_cu.align = align

    return txt_ob


class BDocStyle:
    __slots__ = (
        "size",

        "font",
        "font_bold",
        "font_italic",
        )

    def __init__(self, other=None):
        if other is not None:
            self.inherit(other)

    def inherit(self, other):
        for attr in self.__slots__:
            value = getattr(other, attr)
            setattr(self, attr, value)


class BDocConf:
    __slots__ = (
        # context
        "scene",  # bpy.scene

        "page_width",
        "paragraph_space",
        # TODO, fonts

        # style
        "style_body",
        "style_head1",
        "style_head2",
        "style_head3",
        "style_head4",
        "style_head5",
        )

class BElemABC:
    __slots__ = (
        "data_src",
        "data_dst",
        )
    def to_blend(self, conf, y_pen):
        raise Exception("%r must implement to_blend")


class BElemLineSpace(BElemABC):
    __slots__ = BElemABC.__slots__

    def __init__(self, style_id, fac_y):
        self.data_src = style_id, fac_y

    def to_blend(self, conf, pen_y):
        style_id, fac_y = self.data_src
        style = getattr(conf, style_id)

        return pen_y - (style.size * fac_y)


class BElemText(BElemABC):
    __slots__ = BElemABC.__slots__

    def __init__(self, body, body_fmt, align, indent, style_id):
        self.data_src = body, body_fmt, align, indent, style_id

    def to_blend(self, conf, pen_y):
        body, body_fmt, align, indent, style_id = self.data_src
        txt_ob = butil_text_to_blend(conf, indent, getattr(conf, style_id),
                                     body, body_fmt, align)

        txt_ob.location.y = pen_y
        self.data_dst = txt_ob

        return butil_text_calc_advance(conf.scene, txt_ob)


class BElemListItem(BElemABC):
    __slots__ = BElemABC.__slots__

    def __init__(self, align, indent, style_id, list_type, list_count):
        self.data_src = align, indent, style_id, list_type, list_count

    def to_blend(self, conf, pen_y):
        from docutils.utils import roman

        align, indent, style_id, list_type, list_count = self.data_src
        print(list_type)
        if list_type is None:
            body = " \u2022"
        elif list_type == 'arabic':
            body = " %d. " % (list_count + 1)
        elif list_type == 'loweralpha':
            body = " %s) " % (chr(ord('a') + list_count))
        elif list_type == 'upperalpha':
            body = " %s) " % (chr(ord('A') + list_count))
        elif list_type == 'lowerroman':
            body = "(%s) " % roman.toRoman(list_count + 1).lower()
        elif list_type == 'upperroman':
            body = "(%s) " % roman.toRoman(list_count + 1)
        else:
            raise Exception("unknown enum: %s" % list_type)

        body_fmt = bytearray([0]) * len(body)

        txt_ob = butil_text_to_blend(conf, indent, getattr(conf, style_id),
                                     body, body_fmt, align)

        txt_ob.location.y = pen_y
        self.data_dst = txt_ob

        butil_text_calc_advance(conf.scene, txt_ob)

        # dont advance
        return pen_y


class BlendDoc:
    """ Handle all text conversion quirks
    """
    __slots__ = (
        # flat list of document elements
        "_elems",
        )
    def __init__(self):
        self._elems = []

    def add_elem(self, elem):
        if not isinstance(elem, BElemABC):
            raise Exception("All elems must be 'BElemABC'")
        self._elems.append(elem)

    def to_blend(self, conf):
        y_pen = 0.0
        for elem in self._elems:
            y_pen = elem.to_blend(conf, y_pen)



class Visitor(docutils.nodes.NodeVisitor):
    __slots__ = (
        "document",
        "bdoc",

        "section_level",
        )
    def __init__ (self, doc, bdoc):
        self.document = doc
        self.bdoc = bdoc

        self.section_level = 0
        self.indent = 0

        self.list_types = []
        self.list_count = []  # for numbered lists

        self.body = []
        self.body_fmt = []

        self.is_strong = False
        self.is_emphasis = False

    # -----------------
    # Utility functions
    def as_flag(self):
        return ((1 if self.is_strong else 0) |
                (2 if self.is_emphasis else 0))
    def as_flag_n(self, n):
        return bytearray([self.as_flag()]) * n

    def pop_body(self):
        body = "".join(self.body)
        body_fmt = b"".join(self.body_fmt)

        assert(len(body) == len(body_fmt))

        self.body.clear()
        self.body_fmt.clear()

        return body, body_fmt

    @staticmethod
    def node_align(node):
        align = 'LEFT'

        classes = node.attributes["classes"]
        if "left" in classes:
            align = 'LEFT'
        if "center" in classes:
            align = 'CENTER'
        elif "right" in classes:
            align = 'RIGHT'

        return align

    # -----------------------------
    # Visitors (docutils callbacks)

    def visit_author(self, node):
        print("AUTHOR", node[0])

    # TODO
    def visit_section(self, node):
        self.section_level += 1
    def depart_section(self, node):
        self.section_level -= 1

    def visit_title(self, node):
        print("TITLE", node[0], self.section_level)

    def depart_title(self, node):
        print("/TITLE", node[0])

        body, body_fmt = self.pop_body()
        align = self.node_align(node)
        elem = BElemText(body, body_fmt, align, self.indent, "style_head%d" % self.section_level)
        self.bdoc.add_elem(elem)

        # import IPython
        # IPython.embed()

    def visit_list_item(self, node):
        align = self.node_align(node)
        elem = BElemListItem(align, self.indent, "style_body",
                             self.list_types[-1], self.list_count[-1])
        self.bdoc.add_elem(elem) 

        self.indent += 1
    def depart_list_item(self, node):
        self.list_count[-1] += 1

        self.indent -= 1

    def visit_bullet_list(self, node):
        self.list_types.append(None)
        self.list_count.append(0)
    def depart_bullet_list(self, node):
        item = self.list_types.pop()
        assert(item == None)
        del self.list_count[-1]

    def visit_enumerated_list(self, node):
        self.list_types.append(node["enumtype"])
        self.list_count.append(0)
    def depart_enumerated_list(self, node):
        item = self.list_types.pop()
        assert(item == node["enumtype"])
        del self.list_count[-1]

    def visit_paragraph(self, node):
        # TODO
        pass

    def depart_paragraph(self, node):
        body, body_fmt = self.pop_body()
        align = self.node_align(node)
        elem = BElemText(body, body_fmt, align, self.indent, "style_body")
        self.bdoc.add_elem(elem)

        elem = BElemLineSpace("style_body", 1.0)
        self.bdoc.add_elem(elem)

    def visit_Text(self, node):
        text = node.astext()

        text_ws_sta = text[0].isspace()
        text_ws_end = text[-1].isspace()

        text = " ".join(text.split())

        # add back whitespace on ends
        if text_ws_sta:
            text " " + text
        if text_ws_end:
            text = text + " "

        self.body.append(text)
        text_fmt = self.as_flag_n(len(text))
        self.body_fmt.append(text_fmt)

        assert(len(text) == len(text_fmt))

    def depart_Text(self, node):
        pass

    def visit_strong(self, node):
        self.is_strong = True
    def depart_strong(self, node):
        self.is_strong = False
    def visit_emphasis(self, node):
        self.is_emphasis = True
    def depart_emphasis(self, node):
        self.is_emphasis = False


    def visit_literal_block(self, node):
        pass
    def depart_literal_block(self, node):
        pass

    def visit_code_block(self, node):
        pass
    def depart_code_block(self, node):
        pass

    def visit_date(self, node):
        #date = datetime.date(*(
        #    map(int, unicode(node[0]).split('-'))))
        #metadata['creation_date'] = date
        pass

    #def visit_document(self, node):
    #    print("TEXT:", node.astext())
    #    # metadata['searchable_text'] = node.astext()

    def visit_comment(self, node):
        raise docutils.nodes.SkipNode
    def depart_comment(self, node):
        pass

    def visit_raw(self, node):
        raise docutils.nodes.SkipNode
    def depart_raw(self, node):
        pass



    def unknown_visit(self, node):
        pass
    def unknown_departure(self, node):
        pass


def blend_from_rst(stream):
    bdoc = BlendDoc()

    visitor = Visitor(doc, bdoc)
    doc.walkabout(visitor)

    # setup conversion context
    import bpy
    conf = BDocConf()
    conf.scene = bpy.context.scene
    conf.page_width = 6.0
    conf.paragraph_space = 1.0

    # TODO, make args
    font = bpy.data.fonts.load("/usr/share/fonts/TTF/Vera.ttf")
    font_bold = bpy.data.fonts.load("/usr/share/fonts/TTF/VeraBd.ttf")
    font_italic = bpy.data.fonts.load("/usr/share/fonts/TTF/VeraIt.ttf")

    style = BDocStyle()
    style.size = 1.0
    style.font = font
    style.font_bold = font_bold
    style.font_italic = font_italic

    conf.style_body = BDocStyle(style)
    conf.style_body.size = 0.1

    conf.style_head1 = BDocStyle(style)
    conf.style_head1.size = 0.5

    conf.style_head2 = BDocStyle(style)
    conf.style_head2.size = 0.3

    conf.style_head3 = BDocStyle(style)
    conf.style_head3.size = 0.2

    conf.style_head4 = BDocStyle(style)
    conf.style_head4.size = 0.16

    conf.style_head5 = BDocStyle(style)
    conf.style_head5.size = 0.14

    del style

    visitor.bdoc.to_blend(conf)


if __name__ == "__main__":
    blend_from_rst(doc)

#import IPython
#IPython.embed()
# b --python /src/rst2ps/rst2blend.py


