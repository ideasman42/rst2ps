
#######
rst2ps
#######

rst2ps Is a utility to convert reStructuredText (rst) into a postscript or PDF document.

Its made up of 2 independent modules, ``rst2blend`` and ``blend2ps``.

.. note::

   Currently only ``blend2ps`` is functional.


########
blend2ps
########

This is the component that takes blender scene data and writes it into a postscript file.


How it Works
------------

An orthographic camera is used to define the page size and bounds,
Then curves and images are exported from the current active scene.


Supported Features
------------------

- Orthographic Camera
  *Basic depth is supported, objects are drawn in their order of depth from the camera.*
- Curves (closed, open, bezier and poly lines), _not_ nurbs.
- 3D Text objects (Text is exported as splines rather then text data).
- Materials diffuse color for text & curves.
- Empty objects as images.
- Supported objects from the entire scene are written including dupli's and background sets.


Limitations
-----------

- The postscript files have only been tested with **GhostScript**.
- Currently only single pages can be exposted,
  *GhostScript can join each postscript afterwards.*


Usage
-----

This script can be called directly from the command line or imported into Python,
in both cases it must run from within Blender.

The way images are referenced means you will have to use the ``-dNOSAFER``
argument with ghostscript.

Examples
^^^^^^^^

Export a postscript file from a blend.

.. code-block:: bash

   blender --background mydoc.blend --python blend2ps.py -- --output="mydoc.ps"


Or from Python (running inside Blender)

.. code-block:: python

   import blend2ps
   blend2ps.write("/tmp/myfile.ps")


Convert the postscript into a PDF

.. code-block:: bash

   gs -dAutoRotatePages=/None -dAutoFilterColorImages=false \
      -dNOSAFER -dBATCH -DNOPAUSE -q -sDEVICE=pdfwrite -sOutputFile=out.pdf -f in.ps

#########
rst2blend
#########

TODO
