"""
Specialized tools for the research agent, including LlamaParse, Exa API, and Arxiv API.
"""
import os
from typing import List, Optional

from langchain.tools import tool
from llama_parse import LlamaParse
from exa_py import Exa
import arxiv

# --- Tool Configuration ---

# LlamaParse API Key
LLAMA_CLOUD_API_KEY = os.environ.get("LLAMA_CLOUD_API_KEY")

# Exa API Key
EXA_API_KEY = os.environ.get("EXA_API_KEY")

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
    Searches for academic papers on Arxiv.

    Args:
        query: The query to search for.
        max_results: The maximum number of results to return.

    Returns:
        A list of papers, where each paper is a dictionary.
    """
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
                "published": result.published.isoformat(),
                "pdf_url": result.pdf_url,
                "entry_id": result.entry_id,
            }
        )
    return results

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

