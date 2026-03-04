"""
HTML content parsing utilities
"""

from typing import Optional
from bs4 import BeautifulSoup


def parse_html_content(html: str, parser: str = "lxml") -> BeautifulSoup:
    """
    Parse HTML content into BeautifulSoup object.
    
    Args:
        html: Raw HTML string
        parser: Parser to use (default: lxml)
        
    Returns:
        BeautifulSoup object
    """
    return BeautifulSoup(html, parser)


def extract_article_text(
    soup: BeautifulSoup,
    selectors: Optional[list[str]] = None
) -> str:
    """
    Extract main article text from parsed HTML.
    
    Args:
        soup: BeautifulSoup object
        selectors: List of CSS selectors to try for finding article content
        
    Returns:
        Extracted text content
    """
    if selectors is None:
        # Common article content selectors
        selectors = [
            "article",
            ".article-content",
            ".post-content",
            ".entry-content",
            ".content",
            "main",
            "#content",
        ]
    
    for selector in selectors:
        element = soup.select_one(selector)
        if element:
            # Remove script and style elements
            for tag in element.find_all(["script", "style", "nav", "footer"]):
                tag.decompose()
            
            text = element.get_text(separator="\n", strip=True)
            if text and len(text) > 100:  # Ensure we got meaningful content
                return text
    
    # Fallback: get body text
    body = soup.find("body")
    if body:
        for tag in body.find_all(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return body.get_text(separator="\n", strip=True)
    
    return ""


def extract_meta_description(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract meta description from HTML.
    
    Args:
        soup: BeautifulSoup object
        
    Returns:
        Meta description or None
    """
    # Try og:description first
    og_desc = soup.find("meta", property="og:description")
    if og_desc and og_desc.get("content"):
        return og_desc["content"]
    
    # Try standard meta description
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        return meta_desc["content"]
    
    return None


def extract_title(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract page title from HTML.
    
    Args:
        soup: BeautifulSoup object
        
    Returns:
        Page title or None
    """
    # Try og:title first
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        return og_title["content"]
    
    # Try standard title tag
    title_tag = soup.find("title")
    if title_tag:
        return title_tag.get_text(strip=True)
    
    # Try h1
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    
    return None


def clean_text(text: str, max_length: Optional[int] = None) -> str:
    """
    Clean and normalize text content.
    
    Args:
        text: Raw text
        max_length: Optional maximum length to truncate to
        
    Returns:
        Cleaned text
    """
    # Normalize whitespace
    lines = text.split("\n")
    cleaned_lines = []
    
    for line in lines:
        line = " ".join(line.split())  # Normalize whitespace within line
        if line:
            cleaned_lines.append(line)
    
    result = "\n".join(cleaned_lines)
    
    if max_length and len(result) > max_length:
        # 确保裁剪后加"..."也不超过max_length
        # 为"..."预留3个字符空间
        safe_length = max_length - 3
        result = result[:safe_length].rsplit(" ", 1)[0] + "..."
    
    return result
