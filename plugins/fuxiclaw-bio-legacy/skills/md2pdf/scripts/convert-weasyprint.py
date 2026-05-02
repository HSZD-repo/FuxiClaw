#!/usr/bin/env python3
"""
Markdown to PDF Converter using WeasyPrint
Supports Chinese, code highlighting, tables
"""

import sys
import os
import re
from pathlib import Path

try:
    import markdown
    from weasyprint import HTML, CSS
except ImportError as e:
    print(f"Error: Missing dependency - {e}")
    print("Please run: python3 -m pip install markdown weasyprint")
    sys.exit(1)

def get_css_styles():
    """Return professional CSS styles for PDF"""
    return '''
        @page {
            size: A4;
            margin: 2.5cm 2cm;
            @bottom-center {
                content: counter(page);
                font-size: 9pt;
                color: #666;
            }
        }
        
        body {
            font-family: "Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Micro Hei", "Microsoft YaHei", "PingFang SC", sans-serif;
            font-size: 11pt;
            line-height: 1.8;
            color: #333;
        }
        
        h1, h2, h3, h4, h5, h6 {
            font-weight: 600;
            color: #2c3e50;
            margin-top: 1.5em;
            margin-bottom: 0.5em;
            page-break-after: avoid;
        }
        
        h1 {
            font-size: 24pt;
            border-bottom: 3px solid #3498db;
            padding-bottom: 0.3em;
        }
        
        h2 {
            font-size: 18pt;
            border-bottom: 2px solid #ecf0f1;
            padding-bottom: 0.2em;
        }
        
        h3 {
            font-size: 14pt;
            color: #34495e;
        }
        
        p {
            margin: 0.8em 0;
            text-align: justify;
        }
        
        code {
            font-family: "SF Mono", "Monaco", "Inconsolata", "Fira Code", monospace;
            background-color: #f8f9fa;
            padding: 0.2em 0.4em;
            border-radius: 3px;
            font-size: 0.9em;
            color: #e83e8c;
        }
        
        pre {
            background-color: #2c3e50;
            color: #ecf0f1;
            padding: 1em;
            border-radius: 5px;
            overflow-x: auto;
            font-size: 9pt;
            line-height: 1.5;
            margin: 1em 0;
        }
        
        pre code {
            background-color: transparent;
            color: inherit;
            padding: 0;
        }
        
        blockquote {
            border-left: 4px solid #3498db;
            margin: 1em 0;
            padding: 0.5em 1em;
            background-color: #f8f9fa;
            color: #555;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 1em 0;
            font-size: 10pt;
        }
        
        th, td {
            border: 1px solid #ddd;
            padding: 8px 12px;
            text-align: left;
        }
        
        th {
            background-color: #3498db;
            color: white;
            font-weight: 600;
        }
        
        tr:nth-child(even) {
            background-color: #f8f9fa;
        }
        
        ul, ol {
            margin: 0.5em 0;
            padding-left: 2em;
        }
        
        li {
            margin: 0.3em 0;
        }
        
        a {
            color: #3498db;
            text-decoration: none;
        }
        
        hr {
            border: none;
            border-top: 2px solid #ecf0f1;
            margin: 2em 0;
        }
        
        img {
            max-width: 100%;
            height: auto;
            display: block;
            margin: 1em auto;
        }
    '''

def convert_markdown_to_pdf(input_file, output_file):
    """Convert Markdown file to PDF"""
    
    # Read markdown content
    with open(input_file, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    # Convert markdown to HTML
    html_content = markdown.markdown(
        md_content,
        extensions=[
            'tables',
            'fenced_code',
            'nl2br',
            'sane_lists',
            'toc'
        ]
    )
    
    # Wrap in full HTML document
    title = Path(input_file).stem
    full_html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
</head>
<body>
    {html_content}
</body>
</html>'''
    
    # Convert to PDF
    HTML(string=full_html).write_pdf(
        output_file,
        stylesheets=[CSS(string=get_css_styles())]
    )
    
    return True

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 convert-weasyprint.py <input.md> [output.pdf]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    if len(sys.argv) >= 3:
        output_file = sys.argv[2]
    else:
        output_file = str(Path(input_file).with_suffix('.pdf'))
    
    # Check input file exists
    if not os.path.exists(input_file):
        print(f"Error: Input file not found: {input_file}")
        sys.exit(1)
    
    try:
        convert_markdown_to_pdf(input_file, output_file)
        print(f"✓ Successfully converted: {output_file}")
    except Exception as e:
        print(f"✗ Conversion failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
