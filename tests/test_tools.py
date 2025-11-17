"""
Tests for the specialized tools.
"""
import unittest
from unittest.mock import patch, MagicMock

from myai.tools import (
    llama_parse_tool,
    exa_search_tool,
    arxiv_search_tool,
    pubmed_search_tool,
)

class TestTools(unittest.TestCase):
    """
    Unit tests for the specialized tools.
    """

    @patch("myai.tools.LlamaParse")
    def test_llama_parse_tool(self, mock_llama_parse):
        """
        Tests the LlamaParse tool.
        """
        # Mock the LlamaParse client
        mock_parser = MagicMock()
        mock_parser.load_data.return_value = [MagicMock(to_dict=lambda: {"text": "Parsed content"})]
        mock_llama_parse.return_value = mock_parser

        # Invoke the tool with a dummy API key
        result = llama_parse_tool.invoke({"file_path": "dummy_path.pdf", "api_key": "dummy_key"})
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "Parsed content")

    @patch("myai.tools.Exa")
    def test_exa_search_tool(self, mock_exa):
        """
        Tests the Exa search tool.
        """
        # Mock the Exa client
        mock_exa_client = MagicMock()
        mock_result = MagicMock()
        mock_result.title = "Test Title"
        mock_result.url = "http://example.com"
        mock_result.published_date = "2023-01-01"
        mock_result.author = "Test Author"
        mock_result.score = 1.0
        mock_result.id = "123"
        mock_result.text = "Test text"
        mock_exa_client.search.return_value = MagicMock(results=[mock_result])
        mock_exa.return_value = mock_exa_client

        # Invoke the tool with a dummy API key
        result = exa_search_tool.invoke({"query": "test query", "api_key": "dummy_key"})

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Test Title")

    @patch("myai.tools.arxiv.Search")
    def test_arxiv_search_tool(self, mock_arxiv_search):
        """
        Tests the Arxiv search tool.
        """
        # Mock the Arxiv client
        mock_search = MagicMock()
        mock_result = MagicMock()
        mock_result.title = "Test Paper"
        mock_result.authors = [MagicMock(name="Test Author")]
        mock_result.summary = "Test summary"
        mock_result.published.isoformat.return_value = "2023-01-01T00:00:00"
        mock_result.pdf_url = "http://example.com/paper.pdf"
        mock_result.entry_id = "12345"
        mock_search.results.return_value = [mock_result]
        mock_arxiv_search.return_value = mock_search

        result = arxiv_search_tool.invoke("test query")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Test Paper")

    @patch("myai.tools.requests.get")
    def test_pubmed_search_tool(self, mock_get):
        """Ensures PubMed search parses XML responses."""

        mock_esearch = MagicMock()
        mock_esearch.raise_for_status = MagicMock()
        mock_esearch.json.return_value = {"esearchresult": {"idlist": ["12345"]}}

        mock_efetch = MagicMock()
        mock_efetch.raise_for_status = MagicMock()
        mock_efetch.text = """
            <PubmedArticleSet>
                <PubmedArticle>
                    <MedlineCitation>
                        <PMID>12345</PMID>
                        <Article>
                            <ArticleTitle>Impact of EDTA on E. coli</ArticleTitle>
                            <Abstract>
                                <AbstractText Label=\"Summary\">EDTA disrupts the outer membrane.</AbstractText>
                            </Abstract>
                            <AuthorList>
                                <Author>
                                    <ForeName>Jane</ForeName>
                                    <LastName>Doe</LastName>
                                </Author>
                            </AuthorList>
                            <Journal>
                                <Title>Microbiology Letters</Title>
                                <JournalIssue>
                                    <PubDate>
                                        <Year>2024</Year>
                                        <Month>Jan</Month>
                                        <Day>15</Day>
                                    </PubDate>
                                </JournalIssue>
                            </Journal>
                        </Article>
                    </MedlineCitation>
                </PubmedArticle>
            </PubmedArticleSet>
        """

        mock_get.side_effect = [mock_esearch, mock_efetch]

        results = pubmed_search_tool.invoke({"query": "EDTA"})

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Impact of EDTA on E. coli")
        self.assertIn("EDTA", results[0]["text"])
        self.assertEqual(results[0]["authors"], ["Jane Doe"])

if __name__ == "__main__":
    unittest.main()
