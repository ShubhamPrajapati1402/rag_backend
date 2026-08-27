import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.services.parsers.registry import ParserRegistry
import app.services.parsers  # Trigger registration

files = [
    'data/uploads/dummy.md',
    'data/uploads/dummy.txt',
    'data/uploads/dummy.csv',
    'data/uploads/dummy.xlsx',
    'data/uploads/dummy.json',
    'data/uploads/dummy.html',
    'data/uploads/dummy.xml',
    'data/uploads/dummy.docx',
    'data/uploads/dummy.pptx'
]

for f in files:
    print(f"Testing {f}...")
    try:
        parser = ParserRegistry.get_parser(f)
        elements = parser.parse(f)
        chunks = parser.chunk(elements)
        validator = parser.get_validator()
        report, status, fallback_pages = validator.validate(chunks)
        print(f"[{status}] - {len(elements)} elements, {len(chunks)} chunks")
    except Exception as e:
        print(f"[ERROR] {e}")
    print("-" * 50)
