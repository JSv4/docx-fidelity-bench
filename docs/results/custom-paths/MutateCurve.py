"""Shift only a quadratic curve's control x; preserve text, extent and filled area."""
import sys
from pathlib import Path
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject

reader = PdfReader(Path(sys.argv[1]))
stream = reader.pages[0].get_contents().get_data()
original = b'146.8 620.65 178.25 620.65 209.65 573.7 c'
assert stream.count(original) == 1
# Native output expresses the quadratic as a cubic. Moving the quadratic control
# by 120 path units moves both cubic controls by 120 * 2/3 * 113/600 = 15.0667pt.
changed = stream.replace(original, b'161.8667 620.65 193.3167 620.65 209.65 573.7 c')
writer = PdfWriter(clone_from=reader)
replacement = DecodedStreamObject()
replacement.set_data(changed)
writer.pages[0][NameObject('/Contents')] = writer._add_object(replacement)
writer.write(Path(__file__).with_name('wrong-curve.pdf'))
