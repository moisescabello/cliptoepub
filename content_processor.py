#!/usr/bin/env python3
"""
Content Processor Module for Clipboard to ePub
Handles intelligent content detection and conversion for different formats
"""

import re
import html
import logging
from typing import List, Tuple, Dict, Optional
from datetime import datetime
from urllib.parse import urlparse

# Import third-party libraries
import markdown2
from striprtf.striprtf import rtf_to_text
from bs4 import BeautifulSoup
import requests
from newspaper import Article

# Note: NLTK was previously imported to probe punkt availability, but is not used.


# Module logger
logger = logging.getLogger(__name__)


class ContentDetector:
    """Detects the format of clipboard content"""

    @staticmethod
    def detect_format(content: str) -> str:
        """
        Detect the format of the given content
        Returns: 'url', 'markdown', 'html', 'rtf', or 'plain'
        """
        if not content:
            return 'plain'

        content = content.strip()

        # Check if it's a URL
        if ContentDetector._is_url(content):
            return 'url'

        # Check if it's RTF
        if content.startswith('{\\rtf'):
            return 'rtf'

        # Check if it's HTML
        if ContentDetector._is_html(content):
            return 'html'

        # Check if it's Markdown
        if ContentDetector._is_markdown(content):
            return 'markdown'

        return 'plain'

    @staticmethod
    def _is_url(text: str) -> bool:
        """Check if the text is a valid URL"""
        # Simple check for single-line URLs
        if '\n' in text:
            return False

        try:
            result = urlparse(text)
            return all([result.scheme in ('http', 'https'), result.netloc])
        except (ValueError, AttributeError) as e:
            # Invalid URL format
            logger.debug(f"Invalid URL format: {e}")
            return False

    @staticmethod
    def _is_html(text: str) -> bool:
        """Check if the text contains HTML tags"""
        html_patterns = [
            r'<html[^>]*>',
            r'<body[^>]*>',
            r'<div[^>]*>',
            r'<p[^>]*>',
            r'<span[^>]*>',
            r'<h[1-6][^>]*>'
        ]

        for pattern in html_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True

        # Check for significant amount of HTML-like tags
        tag_count = len(re.findall(r'<[^>]+>', text))
        return tag_count >= 3

    @staticmethod
    def _is_markdown(text: str) -> bool:
        """Check if the text contains Markdown syntax"""
        markdown_patterns = [
            r'^#{1,6}\s+',           # Headers
            r'\*\*[^*]+\*\*',         # Bold
            r'__[^_]+__',             # Bold alternative
            r'\*[^*]+\*',             # Italic
            r'_[^_]+_',               # Italic alternative
            r'^\s*[-*+]\s+',          # Unordered lists
            r'^\s*\d+\.\s+',          # Ordered lists
            r'\[([^\]]+)\]\(([^)]+)\)', # Links
            r'!\[([^\]]*)\]\(([^)]+)\)', # Images
            r'^```',                  # Code blocks
            r'`[^`]+`',              # Inline code
            r'^>\s+',                # Blockquotes
        ]

        score = 0
        for pattern in markdown_patterns:
            if re.search(pattern, text, re.MULTILINE):
                score += 1

        return score >= 2  # At least 2 Markdown patterns


class ContentConverter:
    """Converts different content formats to HTML"""

    def __init__(self):
        self.css_templates = CSSTemplates()

    def convert(self, content: str, format_type: str) -> Tuple[str, Dict]:
        """
        Convert content to HTML based on its format
        Returns: (html_content, metadata)
        """
        converters = {
            'url': self._convert_url,
            'markdown': self._convert_markdown,
            'html': self._convert_html,
            'rtf': self._convert_rtf,
            'plain': self._convert_plain
        }

        converter = converters.get(format_type, self._convert_plain)
        html_content, metadata = converter(content)

        # Apply CSS styling
        styled_html = self._apply_styling(html_content)

        return styled_html, metadata

    def _convert_url(self, url: str) -> Tuple[str, Dict]:
        """Download and extract article content from URL"""
        metadata = {'source': url, 'type': 'web_article'}

        try:
            # Use newspaper3k to extract article with a sane timeout
            try:
                from newspaper import Config  # type: ignore
                cfg = Config()
                # Timeout in seconds for requests inside newspaper3k
                cfg.request_timeout = 10  # type: ignore[attr-defined]
                article = Article(url, config=cfg)
            except Exception:
                # Fallback: construct without Config if unavailable
                article = Article(url)
            article.download()
            article.parse()

            html_content = f"""
            <h1>{html.escape(article.title or 'Untitled Article')}</h1>
            <div class="article-meta">
                <p>Source: <a href="{html.escape(url)}">{html.escape(url)}</a></p>
                {f'<p>Authors: {html.escape(", ".join(article.authors))}</p>' if article.authors else ''}
                {f'<p>Published: {article.publish_date}</p>' if article.publish_date else ''}
            </div>
            <div class="article-content">
                {self._text_to_html_paragraphs(article.text)}
            </div>
            """

            metadata.update({
                'title': article.title,
                'authors': article.authors,
                'publish_date': str(article.publish_date) if article.publish_date else None
            })

            return html_content, metadata

        except Exception as e:
            # Fallback: try simple requests
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, 'html.parser')
                title = soup.find('title')
                title_text = title.text if title else 'Web Page'

                # Remove scripts and styles
                for script in soup(["script", "style"]):
                    script.decompose()

                # Get text content
                text = soup.get_text()
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = '\n'.join(chunk for chunk in chunks if chunk)

                html_content = f"""
                <h1>{html.escape(title_text)}</h1>
                <p class="source">Source: <a href="{html.escape(url)}">{html.escape(url)}</a></p>
                <div class="content">
                    {self._text_to_html_paragraphs(text)}
                </div>
                """

                metadata['title'] = title_text
                return html_content, metadata

            except Exception as e2:
                # Final fallback
                error_html = f"""
                <h1>Error Loading URL</h1>
                <p>Could not load content from: <a href="{html.escape(url)}">{html.escape(url)}</a></p>
                <p>Error: {html.escape(str(e2))}</p>
                """
                return error_html, metadata

    def _convert_markdown(self, content: str) -> Tuple[str, Dict]:
        """Convert Markdown to HTML"""
        metadata = {'type': 'markdown'}

        # Convert using markdown2 with extras for better formatting
        html_content = markdown2.markdown(
            content,
            extras=[
                'fenced-code-blocks',
                'tables',
                'strike',
                'footnotes',
                'smarty-pants',
                'header-ids',
                'code-friendly'
            ]
        )

        # Try to extract title from first H1
        soup = BeautifulSoup(html_content, 'html.parser')
        h1 = soup.find('h1')
        if h1:
            metadata['title'] = h1.get_text()

        return html_content, metadata

    def _convert_html(self, content: str) -> Tuple[str, Dict]:
        """Clean and process HTML content"""
        metadata = {'type': 'html'}

        soup = BeautifulSoup(content, 'html.parser')

        # Extract title if present
        title = soup.find('title')
        if title:
            metadata['title'] = title.text

        # Remove scripts and styles
        for element in soup(['script', 'style', 'meta', 'link']):
            element.decompose()

        # Get body content or full content
        body = soup.find('body')
        if body:
            html_content = str(body)
        else:
            html_content = str(soup)

        return html_content, metadata

    def _convert_rtf(self, content: str) -> Tuple[str, Dict]:
        """Convert RTF to HTML"""
        metadata = {'type': 'rtf'}

        try:
            # Strip RTF formatting to get plain text
            plain_text = rtf_to_text(content)
            # Convert plain text to HTML paragraphs
            html_content = self._text_to_html_paragraphs(plain_text)
        except Exception as e:
            # Fallback to treating as plain text
            html_content = self._text_to_html_paragraphs(content)

        return html_content, metadata

    def _convert_plain(self, content: str) -> Tuple[str, Dict]:
        """Convert plain text to HTML"""
        metadata = {'type': 'plain'}

        # Convert to HTML paragraphs
        html_content = self._text_to_html_paragraphs(content)

        return html_content, metadata

    def _text_to_html_paragraphs(self, text: str) -> str:
        """Convert plain text to HTML paragraphs"""
        # Escape HTML characters
        text = html.escape(text)

        # Convert line breaks to paragraphs
        paragraphs = text.split('\n\n')
        html_paragraphs = []

        for para in paragraphs:
            para = para.strip()
            if para:
                # Convert single line breaks to <br> within paragraphs
                para = para.replace('\n', '<br>')
                html_paragraphs.append(f'<p>{para}</p>')

        return '\n'.join(html_paragraphs)

    def _apply_styling(self, html_content: str) -> str:
        """Apply CSS styling to HTML content"""
        # Wrap content with proper HTML structure if needed
        if not re.search(r'<html[^>]*>', html_content, re.IGNORECASE):
            styled_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        {self.css_templates.get_default_css()}
    </style>
</head>
<body>
    {html_content}
</body>
</html>
            """
        else:
            # Insert CSS into existing HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            head = soup.find('head')
            if not head:
                head = soup.new_tag('head')
                soup.html.insert(0, head)

            style = soup.new_tag('style')
            style.string = self.css_templates.get_default_css()
            head.append(style)

            styled_html = str(soup)

        return styled_html


class ChapterSplitter:
    """Splits long content into chapters"""

    def __init__(self, words_per_chapter: int = 3000):
        self.words_per_chapter = words_per_chapter

    def split_content(self, html_content: str, title: str = None) -> List[Dict]:
        """
        Split HTML content into chapters
        Returns: List of chapter dicts with 'title' and 'content' keys
        """
        soup = BeautifulSoup(html_content, 'html.parser')

        # Try to find natural chapter breaks (h1, h2 tags)
        headings = soup.find_all(['h1', 'h2'])

        if len(headings) > 1:
            # Use headings as natural chapter breaks
            chapters = self._split_by_headings(soup, headings)
        else:
            # Split by word count
            chapters = self._split_by_word_count(soup, title)

        return chapters

    def _split_by_headings(self, soup: BeautifulSoup, headings: List) -> List[Dict]:
        """Split content using headings as chapter boundaries"""
        chapters = []

        for i, heading in enumerate(headings):
            chapter_title = heading.get_text().strip()
            chapter_content = []

            # Collect all elements until the next heading
            current = heading
            while current:
                current = current.find_next_sibling()
                if current and current in headings:
                    break
                if current:
                    chapter_content.append(str(current))

            if chapter_content:
                chapters.append({
                    'title': chapter_title,
                    'content': '\n'.join(chapter_content)
                })

        return chapters if chapters else [{'title': 'Chapter 1', 'content': str(soup)}]

    def _split_by_word_count(self, soup: BeautifulSoup, title: str = None) -> List[Dict]:
        """Split content by word count"""
        text = soup.get_text()
        words = text.split()

        if len(words) <= self.words_per_chapter:
            # Content is short enough for a single chapter
            return [{
                'title': title or 'Chapter 1',
                'content': str(soup)
            }]

        # Split into multiple chapters
        chapters = []
        chapter_num = 1

        # Get all elements
        elements = soup.find_all(['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'ul', 'ol'])

        current_chapter_content = []
        current_word_count = 0

        for element in elements:
            element_text = element.get_text()
            element_word_count = len(element_text.split())

            if current_word_count + element_word_count > self.words_per_chapter and current_chapter_content:
                # Save current chapter
                chapters.append({
                    'title': f'Chapter {chapter_num}',
                    'content': '\n'.join(current_chapter_content)
                })
                chapter_num += 1
                current_chapter_content = []
                current_word_count = 0

            current_chapter_content.append(str(element))
            current_word_count += element_word_count

        # Add remaining content as last chapter
        if current_chapter_content:
            chapters.append({
                'title': f'Chapter {chapter_num}',
                'content': '\n'.join(current_chapter_content)
            })

        return chapters


class TOCGenerator:
    """Generates Table of Contents for ePub"""

    def generate_toc_html(self, chapters: List[Dict], title: str = "Table of Contents") -> str:
        """
        Generate HTML for table of contents

        Args:
            chapters: List of chapter dicts with 'title' keys
            title: Title for the TOC page

        Returns:
            HTML string for the TOC
        """
        toc_items = []

        for i, chapter in enumerate(chapters, 1):
            chapter_title = chapter.get('title', f'Chapter {i}')
            # Create anchor link to chapter
            toc_items.append(f'<li><a href="#chapter_{i}">{html.escape(chapter_title)}</a></li>')

        toc_html = f"""
        <div class="toc">
            <h1>{html.escape(title)}</h1>
            <nav>
                <ul>
                    {''.join(toc_items)}
                </ul>
            </nav>
        </div>
        """

        return toc_html

    def generate_ncx_toc(self, chapters: List[Dict], book_title: str, book_id: str) -> str:
        """
        Generate NCX (Navigation Control for XML) TOC for ePub

        Args:
            chapters: List of chapter dicts
            book_title: Title of the book
            book_id: Unique identifier for the book

        Returns:
            NCX XML string
        """
        nav_points = []

        for i, chapter in enumerate(chapters, 1):
            chapter_title = chapter.get('title', f'Chapter {i}')
            nav_points.append(f"""
            <navPoint id="navpoint-{i}" playOrder="{i}">
                <navLabel>
                    <text>{html.escape(chapter_title)}</text>
                </navLabel>
                <content src="chapter_{i}.xhtml"/>
            </navPoint>
            """)

        ncx_content = f"""<?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN"
         "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">
        <ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
            <head>
                <meta name="dtb:uid" content="{html.escape(book_id)}"/>
                <meta name="dtb:depth" content="1"/>
                <meta name="dtb:totalPageCount" content="0"/>
                <meta name="dtb:maxPageNumber" content="0"/>
            </head>
            <docTitle>
                <text>{html.escape(book_title)}</text>
            </docTitle>
            <navMap>
                {''.join(nav_points)}
            </navMap>
        </ncx>
        """

        return ncx_content

    def add_anchors_to_chapters(self, chapters: List[Dict]) -> List[Dict]:
        """
        Add anchor IDs to chapter headings for TOC linking

        Args:
            chapters: List of chapter dicts with 'content' keys

        Returns:
            Updated chapters with anchored headings
        """
        updated_chapters = []

        for i, chapter in enumerate(chapters, 1):
            content = chapter['content']
            soup = BeautifulSoup(content, 'html.parser')

            # Find the first heading and add an ID
            first_heading = soup.find(['h1', 'h2', 'h3'])
            if first_heading:
                first_heading['id'] = f'chapter_{i}'
            else:
                # If no heading, wrap content in a div with ID
                new_div = soup.new_tag('div', id=f'chapter_{i}')
                new_div.extend(soup.contents[:])
                soup.clear()
                soup.append(new_div)

            updated_chapter = chapter.copy()
            updated_chapter['content'] = str(soup)
            updated_chapters.append(updated_chapter)

        return updated_chapters


class CSSTemplates:
    """Provides CSS templates for ePub styling"""

    def get_default_css(self) -> str:
        """Get the default CSS template"""
        return """
        /* Default ePub CSS Template */
        body {
            font-family: Georgia, 'Times New Roman', serif;
            font-size: 1em;
            line-height: 1.6;
            margin: 1em;
            text-align: justify;
        }

        h1, h2, h3, h4, h5, h6 {
            font-family: 'Helvetica Neue', Arial, sans-serif;
            font-weight: bold;
            line-height: 1.2;
            margin-top: 1.5em;
            margin-bottom: 0.5em;
            text-align: left;
        }

        h1 { font-size: 2em; }
        h2 { font-size: 1.75em; }
        h3 { font-size: 1.5em; }
        h4 { font-size: 1.25em; }
        h5 { font-size: 1.1em; }
        h6 { font-size: 1em; }

        p {
            margin: 0.5em 0 1em 0;
            text-indent: 1.5em;
        }

        p:first-of-type,
        h1 + p, h2 + p, h3 + p, h4 + p, h5 + p, h6 + p {
            text-indent: 0;
        }

        blockquote {
            margin: 1em 2em;
            font-style: italic;
            border-left: 3px solid #ccc;
            padding-left: 1em;
        }

        code {
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
            background-color: #f4f4f4;
            padding: 0.1em 0.3em;
        }

        pre {
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
            background-color: #f4f4f4;
            padding: 1em;
            overflow-x: auto;
            white-space: pre-wrap;
        }

        ul, ol {
            margin: 1em 0;
            padding-left: 2em;
        }

        li {
            margin: 0.5em 0;
        }

        a {
            color: #0066cc;
            text-decoration: underline;
        }

        img {
            max-width: 100%;
            height: auto;
            display: block;
            margin: 1em auto;
        }

        table {
            border-collapse: collapse;
            width: 100%;
            margin: 1em 0;
        }

        th, td {
            border: 1px solid #ddd;
            padding: 0.5em;
            text-align: left;
        }

        th {
            background-color: #f4f4f4;
            font-weight: bold;
        }

        .article-meta {
            font-size: 0.9em;
            color: #666;
            margin: 1em 0;
            padding: 0.5em;
            background-color: #f9f9f9;
            border-radius: 4px;
        }

        .source {
            font-size: 0.9em;
            color: #666;
            font-style: italic;
        }

        .chapter-title {
            page-break-before: always;
            margin-top: 3em;
            margin-bottom: 2em;
            text-align: center;
        }

        .toc {
            page-break-after: always;
        }

        .toc ul {
            list-style: none;
            padding-left: 0;
        }

        .toc li {
            margin: 0.5em 0;
        }

        .toc a {
            text-decoration: none;
            color: inherit;
        }
        """

    def get_minimal_css(self) -> str:
        """Get a minimal CSS template"""
        return """
        /* Minimal ePub CSS Template */
        body {
            font-family: serif;
            font-size: 1em;
            line-height: 1.5;
            margin: 1em;
        }

        h1, h2, h3, h4, h5, h6 {
            font-family: sans-serif;
            margin-top: 1em;
            margin-bottom: 0.5em;
        }

        p {
            margin: 0.5em 0;
        }

        blockquote {
            margin: 1em 2em;
            font-style: italic;
        }

        code, pre {
            font-family: monospace;
        }

        a {
            color: blue;
        }
        """

    def get_modern_css(self) -> str:
        """Get a modern CSS template with better typography"""
        return """
        /* Modern ePub CSS Template */
        @import url('https://fonts.googleapis.com/css2?family=Merriweather:wght@300;400;700&family=Open+Sans:wght@400;600;700&display=swap');

        body {
            font-family: 'Merriweather', Georgia, serif;
            font-size: 1em;
            font-weight: 300;
            line-height: 1.8;
            margin: 1.5em;
            color: #333;
            text-align: justify;
            hyphens: auto;
        }

        h1, h2, h3, h4, h5, h6 {
            font-family: 'Open Sans', 'Helvetica Neue', sans-serif;
            font-weight: 600;
            line-height: 1.3;
            margin-top: 2em;
            margin-bottom: 0.75em;
            color: #111;
            text-align: left;
        }

        h1 {
            font-size: 2.5em;
            font-weight: 700;
            border-bottom: 2px solid #e0e0e0;
            padding-bottom: 0.3em;
        }

        h2 { font-size: 2em; }
        h3 { font-size: 1.5em; }
        h4 { font-size: 1.25em; }

        p {
            margin: 0 0 1.5em 0;
            text-indent: 0;
        }

        p + p {
            text-indent: 1.5em;
        }

        blockquote {
            margin: 2em 0;
            padding: 1em 2em;
            background: linear-gradient(to right, #f7f7f7 0%, #ffffff 100%);
            border-left: 4px solid #4a90e2;
            font-style: italic;
            font-size: 1.05em;
        }

        code {
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 0.85em;
            background: #f5f5f5;
            padding: 0.2em 0.4em;
            border-radius: 3px;
            color: #d14;
        }

        pre {
            background: #2d2d2d;
            color: #f8f8f2;
            padding: 1.5em;
            border-radius: 5px;
            overflow-x: auto;
            font-size: 0.9em;
            line-height: 1.4;
        }

        a {
            color: #4a90e2;
            text-decoration: none;
            border-bottom: 1px dotted #4a90e2;
            transition: color 0.3s ease;
        }

        a:hover {
            color: #357abd;
            border-bottom-style: solid;
        }

        img {
            max-width: 100%;
            height: auto;
            display: block;
            margin: 2em auto;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            border-radius: 4px;
        }

        .drop-cap {
            float: left;
            font-size: 4em;
            line-height: 1;
            margin: 0 0.1em 0 0;
            font-weight: 700;
            color: #4a90e2;
        }
        """

    def get_template(self, name: str = 'default') -> str:
        """Get a CSS template by name"""
        # 1) Prefer a CSS file from templates/<name>.css if present
        try:
            from pathlib import Path
            # Try common locations relative to this file
            here = Path(__file__).resolve()
            candidates = [
                here.parent / 'templates' / f'{name}.css',           # repo root layout (content_processor at root)
                here.parent.parent / 'templates' / f'{name}.css',    # if moved under src/
            ]
            for p in candidates:
                if p.exists() and p.is_file():
                    try:
                        return p.read_text(encoding='utf-8')
                    except Exception:
                        # Fall back to built-ins if file cannot be read
                        break
        except Exception:
            # Path resolution failed; continue with built-ins
            pass

        # 2) Built-in templates
        templates = {
            'default': self.get_default_css,
            'minimal': self.get_minimal_css,
            'modern': self.get_modern_css,
        }
        return templates.get(name, self.get_default_css)()


# Main processing function for integration
def process_clipboard_content(content: str, options: Optional[Dict] = None) -> Dict:
    """
    Main function to process clipboard content

    Args:
        content: The clipboard content to process
        options: Optional processing options (template, chapters, etc.)

    Returns:
        Dictionary with processed content and metadata
    """
    options = options or {}

    # Detect content format
    detector = ContentDetector()
    format_type = detector.detect_format(content)

    # Convert content to HTML
    converter = ContentConverter()
    html_content, metadata = converter.convert(content, format_type)

    # Add format info to metadata
    metadata['detected_format'] = format_type
    metadata['processing_date'] = datetime.now().isoformat()

    # Split into chapters if requested or if content is long
    if options.get('split_chapters', True):
        splitter = ChapterSplitter(words_per_chapter=options.get('words_per_chapter', 3000))
        chapters = splitter.split_content(
            html_content,
            metadata.get('title', 'Untitled')
        )
    else:
        chapters = [{
            'title': metadata.get('title', 'Content'),
            'content': html_content
        }]

    # Generate table of contents if multiple chapters
    toc_generator = TOCGenerator()
    toc_html = None
    if len(chapters) > 1 or options.get('force_toc', False):
        # Add anchors to chapters for TOC linking
        chapters = toc_generator.add_anchors_to_chapters(chapters)
        # Generate TOC HTML
        toc_html = toc_generator.generate_toc_html(chapters)

    # Apply CSS template
    css_template = options.get('css_template', 'default')
    css = CSSTemplates().get_template(css_template)

    return {
        'chapters': chapters,
        'metadata': metadata,
        'css': css,
        'format': format_type,
        'toc_html': toc_html
    }


if __name__ == "__main__":
    # Test the content processor with sample content
    test_contents = [
        "# Sample Markdown\n\nThis is **bold** and this is *italic*.\n\n## Section 2\n\nA [link](https://example.com)",
        "https://example.com",
        "<html><body><h1>HTML Content</h1><p>This is a paragraph.</p></body></html>",
        "This is plain text.\n\nWith multiple paragraphs.\n\nAnd line breaks."
    ]

    for i, content in enumerate(test_contents, 1):
        print(f"\n--- Test {i} ---")
        result = process_clipboard_content(content)
        print(f"Format detected: {result['format']}")
        print(f"Chapters: {len(result['chapters'])}")
        print(f"Metadata: {result['metadata']}")
        print(f"First 200 chars of content: {result['chapters'][0]['content'][:200]}...")
