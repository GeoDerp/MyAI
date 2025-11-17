"""
Specialized tools for the research agent, including LlamaParse, Exa API, and Arxiv API.
"""
import os
from datetime import datetime
from typing import List, Optional
import xml.etree.ElementTree as ET

import requests

from langchain.tools import tool
from llama_parse import LlamaParse
from exa_py import Exa
import arxiv

# --- Tool Configuration ---

# LlamaParse API Key
LLAMA_CLOUD_API_KEY = os.environ.get("LLAMA_CLOUD_API_KEY")

# Exa API Key
EXA_API_KEY = os.environ.get("EXA_API_KEY")

# PubMed / NCBI configuration
NCBI_API_KEY = os.environ.get("NCBI_API_KEY")
NCBI_TOOL_NAME = os.environ.get("NCBI_TOOL_NAME", "myai-research-agent")
NCBI_CONTACT_EMAIL = os.environ.get("NCBI_CONTACT_EMAIL")

PUBMED_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# --- LlamaParse Tool ---

@tool
def llama_parse_tool(file_path: str, api_key: Optional[str] = None) -> List[dict]:
    """
    Parses a PDF document using LlamaParse and returns a list of structured documents.

    Args:
        file_path: The path to the PDF file to parse.
        api_key: The LlamaParse API key. If not provided, it will be read from the LLAMA_CLOUD_API_KEY environment variable.

    Returns:
        A list of structured documents, where each document is a dictionary.
    """
    api_key = api_key or os.environ.get("LLAMA_CLOUD_API_KEY")
    if not api_key:
        # LlamaParse key missing — log and return empty results so the agent can continue.
        print("[WARN llama_parse_tool] LLAMA_CLOUD_API_KEY not set; skipping PDF parsing and returning [].")
        return []
    
    parser = LlamaParse(api_key=api_key, result_type="markdown")
    # Use the parser to load data and return its structured representation.
    try:
        parsed = parser.load_data(file_path)
        # Convert objects to plain dicts if they provide to_dict()
        out = []
        for p in parsed or []:
            try:
                if hasattr(p, "to_dict"):
                    out.append(p.to_dict())
                elif isinstance(p, dict):
                    out.append(p)
                else:
                    # Fallback: coerce to dict-like via __dict__ if possible
                    out.append(dict(p))
            except Exception:
                out.append(p)
        return out
    except Exception as e:
        print(f"[ERROR llama_parse_tool] Parser failed: {e}")
        return []

# --- Exa API Tool ---

@tool
def exa_search_tool(query: str, num_results: int = 5, api_key: Optional[str] = None) -> List[dict]:
    """
    Performs a semantic search using the Exa API.

    Args:
        query: The query to search for.
        num_results: The number of results to return.
        api_key: The Exa API key. If not provided, it will be read from the EXA_API_KEY environment variable.

    Returns:
        A list of search results, where each result is a dictionary.
    """
    api_key = api_key or os.environ.get("EXA_API_KEY")
    # Debug: log what api_key the tool received and what the environment has at call time
    print(f"[DEBUG exa_search_tool] api_key param: {api_key!r}, ENV EXA_API_KEY: {os.environ.get('EXA_API_KEY')!r}")
    if not api_key:
        # Exa key missing — warn and return empty results so the agent can continue with other sources.
        print("[WARN exa_search_tool] EXA_API_KEY not set; skipping Exa search and returning [].")
        return []

    exa = Exa(api_key=api_key)
    results = exa.search(query, num_results=num_results, use_autoprompt=True)
    return [
        {
            "title": result.title,
            "url": result.url,
            "published_date": result.published_date,
            "author": result.author,
            "score": result.score,
            "id": result.id,
            "text": result.text,
        }
        for result in results.results
    ]

# --- Arxiv API Tool ---

@tool
def arxiv_search_tool(query: str, max_results: int = 5) -> List[dict]:
    """
    Searches for academic papers on Arxiv with exponential backoff for rate limiting.

    Args:
        query: The query to search for.
        max_results: The maximum number of results to return.

    Returns:
        A list of papers, where each paper is a dictionary with proper url/source fields.
    """
    import time
    from urllib.error import HTTPError
    
    max_retries = 5
    base_delay = 3  # Start with 3 seconds
    
    for attempt in range(max_retries):
        try:
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.Relevance,
            )
            
            results = []
            for result in search.results():
                results.append(
                    {
                        "title": result.title,
                        "authors": [author.name for author in result.authors],
                        "summary": result.summary,
                        "text": result.summary,  # Add 'text' field for consistency
                        "published": result.published.isoformat(),
                        "pdf_url": result.pdf_url,
                        "url": result.entry_id,  # Add 'url' field pointing to arxiv entry
                        "source": "arxiv.org",   # Add 'source' field
                        "entry_id": result.entry_id,
                    }
                )
            
            print(f"[ArXiv] Successfully retrieved {len(results)} papers for query: {query[:60]}...")
            return results
            
        except HTTPError as e:
            if e.code == 429:  # Rate limit exceeded
                if attempt < max_retries - 1:
                    # Exponential backoff: 3s, 6s, 12s, 24s
                    delay = base_delay * (2 ** attempt)
                    print(f"[ArXiv] Rate limit hit (429). Retrying in {delay}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                else:
                    print(f"[ArXiv] Rate limit exceeded after {max_retries} attempts. Returning empty results.")
                    return []  # Return empty list instead of crashing
            else:
                # Other HTTP errors
                print(f"[ArXiv] HTTP error {e.code}: {e.reason}. Returning empty results.")
                return []
                
        except Exception as e:
            # Catch any other errors (network issues, parsing errors, etc.)
            print(f"[ArXiv] Unexpected error: {type(e).__name__}: {e}. Returning empty results.")
            return []
    
    # If we exhausted all retries
    print(f"[ArXiv] All retry attempts exhausted. Returning empty results.")
    return []


def _pubmed_common_params() -> dict:
    params = {}
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY
    if NCBI_TOOL_NAME:
        params["tool"] = NCBI_TOOL_NAME
    if NCBI_CONTACT_EMAIL:
        params["email"] = NCBI_CONTACT_EMAIL
    return params


def _pubmed_date_to_iso(pub_date_elem: ET.Element | None) -> Optional[str]:
    if pub_date_elem is None:
        return None

    year = (pub_date_elem.findtext("Year") or "").strip()
    if not year:
        medline = pub_date_elem.findtext("MedlineDate")
        return medline.strip() if medline else None

    month_raw = (pub_date_elem.findtext("Month") or "").strip()
    day_raw = (pub_date_elem.findtext("Day") or "").strip()
    month_lookup = {
        "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
        "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
        "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
    }
    month = month_lookup.get(month_raw[:3], "01") if month_raw else "01"
    day = day_raw if day_raw.isdigit() else "01"
    try:
        dt = datetime(int(year), int(month), int(day))
        return dt.date().isoformat()
    except ValueError:
        return year


def _extract_pubmed_abstract(article_elem: ET.Element) -> str:
    abstract_parts = []
    for abs_elem in article_elem.findall(".//Article/Abstract/AbstractText"):
        text = "".join(abs_elem.itertext()).strip()
        label = abs_elem.get("Label")
        if label:
            text = f"{label}: {text}" if text else label
        if text:
            abstract_parts.append(text)
    return "\n".join(abstract_parts)


def _extract_pubmed_authors(article_elem: ET.Element) -> List[str]:
    authors = []
    for author in article_elem.findall(".//Article/AuthorList/Author"):
        collective = author.findtext("CollectiveName")
        if collective:
            name = collective.strip()
        else:
            first = author.findtext("ForeName") or author.findtext("Initials")
            last = author.findtext("LastName")
            parts = [part.strip() for part in (first, last) if part]
            name = " ".join(parts)
        if name:
            authors.append(name)
    return authors


def _extract_keywords_from_question(question: str) -> str:
    """Extract scientific keywords from a natural language question for PubMed search.
    
    PubMed works better with keywords than full questions. This function removes
    question words and common phrases while preserving scientific terminology.
    """
    import re
    
    # First, normalize scientific terms before lowercasing
    # Replace "ecoli" or "e coli" with proper "E. coli"
    question = re.sub(r'\be\.?\s*coli\b', 'E. coli', question, flags=re.IGNORECASE)
    
    # Now process the question
    keywords = question
    
    # Remove question starters (case insensitive)
    keywords = re.sub(r'^\s*(what|how|why|when|where|who|which|does|do|is|are|can)\s+(is|are|does|do|happens?|occurs?|affects?|causes?|results?|leads to|key aspects|aspects)\s+', '', keywords, flags=re.IGNORECASE)
    keywords = re.sub(r'^\s*(what|how|why|when|where|who|which)\s+', '', keywords, flags=re.IGNORECASE)
    
    # Remove filler phrases and words
    keywords = re.sub(r'\b(the|a|an|in|on|at|to|for|of|with|from|by|about|when|left|placed|put|added|happens|occur|results?|leads to|what|key|aspects)\b', ' ', keywords, flags=re.IGNORECASE)
    
    # Remove question marks and extra punctuation at the end
    keywords = re.sub(r'[?!;:]+$', '', keywords)
    
    # Clean up extra spaces
    keywords = ' '.join(keywords.split())
    
    return keywords if keywords else question


@tool
def pubmed_search_tool(query: str, max_results: int = 5) -> List[dict]:
    """Searches the PubMed biomedical literature database.

    Args:
        query: Biomedical search query (can be a question or keywords).
        max_results: Maximum number of PubMed articles to return.

    Returns:
        A list of article dictionaries containing metadata and abstract text.
    """

    if not query:
        return []

    # Extract keywords from natural language questions for better PubMed matching
    search_term = _extract_keywords_from_question(query)
    print(f"[DEBUG pubmed] Original query: {query}")
    print(f"[DEBUG pubmed] Search term: {search_term}")

    params = {
        "db": "pubmed",
        "term": search_term,
        "retmode": "json",
        "retmax": max_results,
        "sort": "relevance",
    }
    params.update(_pubmed_common_params())

    try:
        esearch_resp = requests.get(PUBMED_ESEARCH_URL, params=params, timeout=15)
        esearch_resp.raise_for_status()
        data = esearch_resp.json()
        id_list = data.get("esearchresult", {}).get("idlist", [])
    except Exception as exc:
        print(f"[WARN pubmed_search_tool] esearch failed: {exc}; returning [].")
        return []

    if not id_list:
        return []

    fetch_params = {
        "db": "pubmed",
        "id": ",".join(id_list),
        "retmode": "xml",
    }
    fetch_params.update(_pubmed_common_params())

    try:
        efetch_resp = requests.get(PUBMED_EFETCH_URL, params=fetch_params, timeout=20)
        efetch_resp.raise_for_status()
        root = ET.fromstring(efetch_resp.text)
    except Exception as exc:
        print(f"[WARN pubmed_search_tool] efetch failed: {exc}; returning [].")
        return []

    articles = []
    for article in root.findall(".//PubmedArticle"):
        pmid = (article.findtext(".//MedlineCitation/PMID") or "").strip()
        title = (article.findtext(".//Article/ArticleTitle") or "").strip()
        abstract_text = _extract_pubmed_abstract(article)
        authors = _extract_pubmed_authors(article)
        pub_date = _pubmed_date_to_iso(article.find(".//JournalIssue/PubDate"))
        journal = (article.findtext(".//Journal/Title") or "").strip()

        entry = {
            "title": title or f"PubMed Article {pmid}",
            "authors": authors,
            "summary": abstract_text,
            "text": abstract_text,
            "published": pub_date,
            "journal": journal,
            "pmid": pmid,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None,
            "source": "pubmed.ncbi.nlm.nih.gov",
        }
        if abstract_text:
            articles.append(entry)
        else:
            # Even without an abstract we keep minimal metadata for completeness.
            entry["text"] = entry["summary"] = journal or ""
            articles.append(entry)

    return articles

# Example usage:
if __name__ == "__main__":
    # Note: These examples require API keys to be set as environment variables.
    
    # Example: Exa Search
    try:
        exa_results = exa_search_tool.invoke("What is LangGraph?")
        print("Exa Search Results:")
        for res in exa_results:
            print(f"- {res['title']}: {res['url']}")
    except ValueError as e:
        print(e)

    # Example: Arxiv Search
    try:
        arxiv_results = arxiv_search_tool.invoke("large language models")
        print("\nArxiv Search Results:")
        for res in arxiv_results:
            print(f"- {res['title']}: {res['pdf_url']}")
    except Exception as e:
        print(e)
        
    # Example: LlamaParse (requires a PDF file)
    # To run this, create a dummy PDF file named "example.pdf"
    if LLAMA_CLOUD_API_KEY:
        try:
            with open("example.pdf", "w") as f:
                f.write("This is a dummy PDF.")
            
            parsed_docs = llama_parse_tool.invoke("example.pdf")
            print("\nLlamaParse Results:")
            print(parsed_docs)
            
            os.remove("example.pdf")
        except Exception as e:
            print(f"LlamaParse example failed: {e}")

