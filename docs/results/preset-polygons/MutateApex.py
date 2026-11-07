"""Change only the adjusted triangle's painted apex; preserve text, bounds and area."""
import sys
from pathlib import Path
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject

source = Path(sys.argv[1])
reader = PdfReader(source)
stream = reader.pages[0].get_contents().get_data()
original = b'111.9 648 l 163.05 606.95 l 90 606.95 l h'
assert stream.count(original) == 1
changed = stream.replace(original, b'126.525 648 l 163.05 606.95 l 90 606.95 l h')
writer = PdfWriter(clone_from=reader)
replacement = DecodedStreamObject()
replacement.set_data(changed)
writer.pages[0][NameObject('/Contents')] = writer._add_object(replacement)
writer.write(Path(__file__).with_name('wrong-apex.pdf'))
