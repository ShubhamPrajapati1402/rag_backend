from app.services.parsers.registry import ParserRegistry
from app.services.parsers.pdf_parser import PDFParser
from app.services.parsers.markdown_parser import MarkdownParser
from app.services.parsers.txt_parser import TXTParser
from app.services.parsers.csv_parser import CSVParser
from app.services.parsers.excel_parser import ExcelParser
from app.services.parsers.json_parser import JSONParser
from app.services.parsers.docx_parser import DOCXParser
from app.services.parsers.html_parser import HTMLParser
from app.services.parsers.xml_parser import XMLParser
from app.services.parsers.pptx_parser import PPTXParser

# Register known parsers here
ParserRegistry.register(".pdf", PDFParser)
ParserRegistry.register(".md", MarkdownParser)
ParserRegistry.register(".txt", TXTParser)
ParserRegistry.register(".csv", CSVParser)
ParserRegistry.register(".tsv", CSVParser)
ParserRegistry.register(".xlsx", ExcelParser)
ParserRegistry.register(".xls", ExcelParser)
ParserRegistry.register(".json", JSONParser)
ParserRegistry.register(".docx", DOCXParser)
ParserRegistry.register(".html", HTMLParser)
ParserRegistry.register(".htm", HTMLParser)
ParserRegistry.register(".xml", XMLParser)
ParserRegistry.register(".pptx", PPTXParser)
ParserRegistry.register(".ppt", PPTXParser)
