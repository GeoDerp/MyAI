"""
MCP (Model Context Protocol) Integration for Research Agent

This module demonstrates how to integrate MCP servers to extend
the research agent's capabilities with additional tools.
"""
from typing import Optional
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServer
from myai._research_agent import ResearchDependencies, FinalAnswer


def create_research_agent_with_mcp(
    mcp_servers: Optional[list[str]] = None
) -> Agent[ResearchDependencies, FinalAnswer]:
    """
    Create a research agent with MCP server integration.
    
    Args:
        mcp_servers: List of MCP server URLs or configurations
        
    Returns:
        Configured research agent with MCP tools
    """
    if mcp_servers is None:
        mcp_servers = []
    
    # Convert string URLs to MCPServer objects
    mcp_server_objects = []
    for server in mcp_servers:
        if isinstance(server, str):
            # Assume it's a URL
            mcp_server_objects.append(MCPServer(url=server))
        else:
            mcp_server_objects.append(server)
    
    agent = Agent(
        'openai:gpt-4o',
        deps_type=ResearchDependencies,
        output_type=FinalAnswer,
        mcp_servers=mcp_server_objects,
        instructions="""You are a research assistant with access to enhanced tools via MCP.

Use MCP tools when appropriate:
- File system access for local documents
- Database queries for structured data
- Custom APIs for specialized information

Always combine MCP tools with web search for comprehensive research.
""",
    )
    
    return agent


# Example MCP Server Configurations
MCP_SERVER_EXAMPLES = {
    "filesystem": {
        "description": "Access to local file system for reading research papers",
        "url": "http://localhost:8000/mcp",
        "use_case": "Reading local PDFs, markdown files, research notes"
    },
    "database": {
        "description": "Query research databases",
        "url": "http://localhost:8001/mcp",
        "use_case": "Structured data queries, citation databases"
    },
    "arxiv": {
        "description": "Direct arXiv API access",
        "url": "http://localhost:8002/mcp",
        "use_case": "Academic paper search and retrieval"
    },
    "wikipedia": {
        "description": "Wikipedia API with citation support",
        "url": "http://localhost:8003/mcp",
        "use_case": "Encyclopedia queries with references"
    }
}


def print_mcp_examples():
    """Print example MCP server configurations"""
    print("\n" + "="*80)
    print("EXAMPLE MCP SERVER INTEGRATIONS")
    print("="*80)
    
    for name, info in MCP_SERVER_EXAMPLES.items():
        print(f"\n{name.upper()}:")
        print(f"  Description: {info['description']}")
        print(f"  URL: {info['url']}")
        print(f"  Use Case: {info['use_case']}")
    
    print("\n" + "="*80)
    print("\nTo use MCP servers:")
    print("1. Start your MCP servers (see https://modelcontextprotocol.io/)")
    print("2. Pass URLs to create_research_agent_with_mcp()")
    print("3. Agent will automatically discover and use available tools")
    print("="*80 + "\n")


def print_ethical_guidelines():
    """Print ethical guidelines for MCP integration"""
    ETHICAL_MCP_GUIDELINES = """
    When integrating MCP servers, follow these ethical guidelines:

    1. PRIVACY
       - Don't expose sensitive file systems without proper authentication
       - Respect user privacy and data protection regulations
       - Log access to sensitive resources

    2. SECURITY
       - Use proper authentication for MCP servers
       - Validate all inputs to prevent injection attacks
       - Run MCP servers in isolated environments

    3. TRANSPARENCY
       - Clearly document what data MCP servers can access
       - Inform users when their local files/data are being accessed
       - Log all MCP tool calls for audit purposes

    4. RATE LIMITING
       - Implement rate limits to prevent abuse
       - Respect external API terms of service
       - Cache results where appropriate

    5. DATA HANDLING
       - Don't store sensitive data unnecessarily
       - Encrypt data in transit and at rest
       - Provide data deletion mechanisms
    """
    print("="*80)
    print("ETHICAL MCP SERVER GUIDELINES")
    print("="*80)
    print(ETHICAL_MCP_GUIDELINES)
    print("="*80)
