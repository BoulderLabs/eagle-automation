#!/usr/bin/env python

"""pea diff: compare CadSoft Eagle files

USAGE: {prog} {command} [--page=N] [--output=F] [--semantic] <from-file> <to-file>

Parameters:
    <from-file>  File to diff from
    <to-file>      File to diff to

Options:
    -p,--page=N    Page to compare on multi-page schematics [default: 1]
    -o,--output=F  File to output diff into
    -s,--semantic  Do a semantic diff (for library diffs)

Copyright (C) 2015  Bernard Pratz <guyzmo+github@m0g.net>
Copyright (C) 2014  Tomaz Solc <tomaz.solc@tablix.org>
"""

from __future__ import print_function

import os
import sys
import docopt
import difflib
import tempfile
import subprocess
import pyeagle

import logging

log = logging.getLogger('pea').getChild(__name__)

from PIL import Image, ImageOps, ImageChops, ImageDraw, ImageFont

from eagle_automation.config import config
from eagle_automation.export import get_extension, BadExtension, EaglePNGExport, EagleDirectoryExport


def to_png(in_path, page):
    with tempfile.TemporaryDirectory() as workdir:
        extension = in_path.split('.')[-1].lower()
        if extension == 'brd':
            layers = config.LAYERS.values()
            out_paths = [os.path.join(workdir, '%04d-' % i + layer + '.png')
                         for i, layer in enumerate(config.LAYERS.keys()) ]
        elif extension == 'sch':
            layers = [{'layers': ['ALL']}]
            out_paths = [os.path.join(workdir, 'all.png')]
        else:
            os.rmdir(workdir)
            raise BadExtension

        export = EaglePNGExport(workdir=workdir)
        export.set_page(page)
        export.export(in_path, layers, out_paths)

        oim = {}
        for i, out_path in enumerate(out_paths):
            im = Image.open(out_path).convert("L")
            oim[os.path.basename(out_path)] = im
            os.unlink(out_path)

        return oim


def to_txt(in_path):
    with tempfile.TemporaryDirectory() as workdir:
        out_path = os.path.join(workdir, "out.txt")

        export = EagleDirectoryExport()
        export.export(in_path, None, [out_path])

        directory = open(out_path).read()
        return directory


def pdf_concatenate(fname, files):
    from PyPDF2 import PdfFileWriter, PdfFileReader

    def append_pdf(input, output):
        [output.addPage(input.getPage(page_num)) for page_num in range(input.numPages)]

    output = PdfFileWriter()

    for f in files:
        append_pdf(PdfFileReader(open(f, "rb")), output)

    with open(fname, "wb") as f:
        output.write(f)


def diff_visual(from_file, to_file, page=0, output=None):
    with tempfile.TemporaryDirectory() as workdir:
        pages = []
        first = last = 1
        preview = False

        if not output:
            output = os.path.join(
                workdir,
                "{from_file}-{to_file}.pdf".format(from_file=os.path.basename(from_file).split('.')[0],
                                                   to_file=os.path.basename(to_file).split('.')[0])
            )
            preview = True

        if not page:
            try:
                with open(from_file) as _from:
                    with open(to_file) as _to:
                        _from = _from.read()
                        _to = _to.read()
                        # TODO use pyeagle!
                        if not '<schematic' in _from and not '<board' in _from:
                            raise SyntaxError('File {} is not an eagle/xml design file!'.format(from_file))
                        if not '<schematic' in _to and not '<board' in _to:
                            raise SyntaxError('File {} is not an eagle/xml design file!'.format(to_file))
                        if not _from.count('<sheet>') == _to.count('<sheet>'):
                            raise Exception(
                                'File {} does not have the same number of sheets as {}'.format(from_file, to_file))
                        last = _from.count('<sheet>') or _from.count('<board')
            except Exception as err:
                log.warning(err.message)
                log.warning("Considering file as an Eagle v5 binary format.")
                first = last = page
        else:
            first = last = page

        for page in range(first, last + 1):
            log.info("Checking page {} of {}".format(page, last))

            a_im_l = to_png(from_file, page=page)
            b_im_l = to_png(to_file, page=page)

            bbox = None
            for k in sorted(a_im_l.keys()):
                a_im = a_im_l[k]
                b_im = b_im_l[k]

                # make the sizes equal
                # if a sheet contains the filename, it is updated with the temporary name
                # and may thus change the size of the image
                width = max((a_im.size[0], b_im.size[0]))
                height = max((a_im.size[1], b_im.size[1]))
                a_im2 = Image.new("L", (width, height))
                a_im2.paste(a_im, (0, 0))
                a_im = a_im2
                a_im2 = None
                b_im2 = Image.new("L", (width, height))
                b_im2.paste(b_im, (0, 0))
                b_im = b_im2
                b_im2 = None

                if bbox is None:
                    bb_a = a_im.getbbox()
                    bb_b = b_im.getbbox()
                    bbox = (min(bb_a[0], bb_b[0]),
                            min(bb_a[1], bb_b[1]),
                            max(bb_a[2], bb_b[2]),
                            max(bb_a[3], bb_b[3]))
                if bbox:
                    a_im = a_im.crop( bbox )
                    b_im = b_im.crop( bbox )

                added = ImageOps.autocontrast(ImageChops.subtract(b_im, a_im), 0)
                deled = ImageOps.autocontrast(ImageChops.subtract(a_im, b_im), 0)

                a_mask = added.point(lambda p: p == 0 and 255).convert("1")
                d_mask = deled.point(lambda p: p == 0 and 255).convert("1")

                deled = ImageOps.colorize(deled, "#000", "#33f")
                added = ImageOps.colorize(added, "#000", "#f33")
                same = ImageOps.colorize(a_im, "#000", "#aaa")

                c1 = ImageChops.composite(same, deled, d_mask)
                im = ImageChops.composite(c1, added, a_mask)
                font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 32)
                ImageDraw.Draw(im).text( (20,20), '%s' % k[5:-4], (0, 255, 0), font=font)
                fname = "{from_file}-{to_file}-page_{page}-{type}.pdf".format(
                    from_file=os.path.basename(from_file.split('.')[0]),
                    to_file=os.path.basename(to_file.split('.')[0]),
                    page=page,
                    type=k)
                im.save(os.path.join(workdir, fname))
                pages.append(os.path.join(workdir, fname))

        if len(pages) > 0:
            pdf_concatenate(output, pages)
            log.info("Diff output in file: {}".format(output))
            if preview:
                try:
                    subprocess.call([config.OPEN, output])
                except FileNotFoundError as err:
                    log.warning("Cannot find open utility: `{}`".format(config.OPEN))
                    log.warning("Open your file manually to check it")
                #input("Press enter to flush all outputs")
        else:
            log.error("No diff output.")

        #workdir.cleanup()


def diff_text(from_file, to_file):
    a_txt = to_txt(from_file)
    b_txt = to_txt(to_file)

    a_lines = a_txt.split('\n')
    b_lines = b_txt.split('\n')

    diff = difflib.unified_diff(a_lines, b_lines, fromfile=from_file, tofile=to_file, lineterm='')
    print('\n'.join(list(diff)))


def diff_packages(libf, libt):
    """
    Print the differences in _packages_ between two libraries
    :param libf: pyeagle open'd lib
    :param libt: pyeagle open'd lib
    :return: nothing, this prints directly
    """
    packs_f = set(libf.packages)
    packs_t = set(libt.packages)
    missing_new = packs_f.difference(packs_t)
    missing_old = packs_t.difference(packs_f)
    if missing_new:
        print("Packages in old %s not in new %s:" % (libf.from_file, libt.from_file))
        [print(x) for x in missing_new]
    if missing_old:
        print("Packages missing from old %s that were in new %s:" % (libf.from_file, libt.from_file))
        [print(x) for x in missing_old]
    # Now, for all x that _are_ in both, need to compare them!
    for p in packs_f.intersection(packs_t):
        # diff pads and primitives here.
        real_f = libf.packages[p]
        real_t = libt.packages[p]
        if len(real_f.pads) != len(real_t.pads):
            print("Different pad count for part: %s" % p)
            # TODO - print the different ones one day?
            continue
        # More likely, the pads themselves changed...
        # make new sets keyed on the pad names, then compare them on that.
        # oops, python 3 alert! dict comprehensions!
        pads_f = {x.name:x for x in real_f.pads}
        pads_t = {x.name:x for x in real_t.pads}
        for key, a in pads_f.items():
            b = pads_t[key]
            if (repr(a) != repr(b)):
                print("Package: %s Pads differ: %s != %s" % (p, a, b))
        # FIXME! - no comparison of other primitives!


def diff_devices(libf, libt):
    devs_f = set(libf.device_sets)
    devs_t = set(libt.device_sets)
    # TODO - unconvinced this is complete :|
    missing_new = devs_f.difference(devs_t)
    missing_old = devs_t.difference(devs_f)
    if missing_new:
        print("Devices in old %s not in new %s:" % (libf.from_file, libt.from_file))
        [print(x) for x in missing_new]
    if missing_old:
        print("Devices missing from old %s that were in new %s:" % (libf.from_file, libt.from_file))
        [print(x) for x in missing_old]
    # Now, for all x that _are_ in both, need to compare them!


def diff_semantic(from_file, to_file):
    # make a list of packages first, and immediately output for/against
    libf = pyeagle.open(from_file)
    libt = pyeagle.open(to_file)
    diff_packages(libf, libt)
    diff_devices(libf, libt)


def diff(from_file, to_file, page=0, output=None, semantic=False):
    extension = get_extension(from_file)

    if get_extension(to_file) != extension:
        log.error("%s: both files should have the same extension" % (to_file,))
        return

    if extension == 'brd':
        diff_visual(from_file, to_file, page, output)
    elif extension == 'sch':
        diff_visual(from_file, to_file, page, output)
    elif extension == 'lbr':
        if semantic or config.SEMANTIC_DIFF:
            diff_text(from_file, to_file)
        else:
            diff_semantic(from_file, to_file)
    else:
        log.error("%s: skipping, not a board or schematic" % (from_file,))
        return


################################################################################

def diff_main(verbose=False):
    args = docopt.docopt(__doc__.format(prog=sys.argv[0], command=sys.argv[1]))
    log.debug("Arguments:\n{}".format(repr(args)))

    diff(args['<from-file>'], args['<to-file>'], int(args['--page'] if args['--page'] else 0), args['--output'], args['--semantic'])


if __name__ == '__main__':
    diff_main()
