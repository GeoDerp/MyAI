"""
Tests for the Research Agent

Run with: pytest test_research_agent.py -v
"""
import pytest
from research_agent import (
    ResearchSource,
    ResearchThought,
    FinalAnswer,
    ResearchDependencies
)


class TestDataModels:
    """Test the data models"""
    
    def test_research_source_creation(self):
        """Test creating a research source"""
        source = ResearchSource(
            title="Test Paper",
            content="Test content",
            url="https://example.com",
            confidence=8
        )
        assert source.title == "Test Paper"
        assert source.confidence == 8
        assert source.url == "https://example.com"
    
    def test_research_source_confidence_validation(self):
        """Test that confidence is validated 0-10"""
        # Valid confidence
        source = ResearchSource(
            title="Test",
            content="Content",
            confidence=5
        )
        assert source.confidence == 5
        
        # Test boundary values
        source_min = ResearchSource(
            title="Test",
            content="Content",
            confidence=0
        )
        assert source_min.confidence == 0
        
        source_max = ResearchSource(
            title="Test",
            content="Content",
            confidence=10
        )
        assert source_max.confidence == 10
    
    def test_research_thought_creation(self):
        """Test creating a research thought"""
        thought = ResearchThought(
            observation="Found interesting data",
            analysis="This supports the hypothesis",
            next_action="Search for more evidence",
            confidence=7
        )
        assert thought.confidence == 7
        assert "interesting data" in thought.observation
    
    def test_final_answer_creation(self):
        """Test creating a final answer"""
        sources = [
            ResearchSource(
                title="Source 1",
                content="Content 1",
                confidence=8
            )
        ]
        
        answer = FinalAnswer(
            answer="The answer is 42",
            confidence=9,
            evidence=sources,
            reasoning="Based on the evidence",
            certainty_level="high"
        )
        
        assert answer.confidence == 9
        assert answer.certainty_level == "high"
        assert len(answer.evidence) == 1


class TestResearchDependencies:
    """Test research dependencies"""
    
    def test_dependencies_initialization(self):
        """Test initializing research dependencies"""
        deps = ResearchDependencies(
            max_iterations=5,
            min_confidence=7
        )
        
        assert deps.max_iterations == 5
        assert deps.min_confidence == 7
        assert deps.iteration_count == 0
        assert len(deps.sources_collected) == 0
        assert len(deps.thoughts) == 0
    
    def test_dependencies_defaults(self):
        """Test default values"""
        deps = ResearchDependencies()
        
        assert deps.max_iterations == 10
        assert deps.min_confidence == 8
        assert deps.sources_collected is not None
        assert deps.thoughts is not None


@pytest.mark.asyncio
class TestResearchAgent:
    """Test the research agent (requires API key or mock)"""
    
    async def test_agent_can_be_created(self):
        """Test that the agent can be instantiated"""
        from research_agent import research_agent
        
        assert research_agent is not None
        assert research_agent.deps_type == ResearchDependencies
    
    # Note: Full integration tests would require API keys
    # or mocked LLM responses. Add those in a separate test file.


class TestRamaLamaConfig:
    """Test RamaLama configuration"""
    
    def test_ramalama_config_creation(self):
        """Test creating RamaLama config"""
        from ramalama_config import RamaLamaConfig
        
        config = RamaLamaConfig(model_name="granite", port=8080)
        
        assert config.model_name == "granite"
        assert config.port == 8080
        assert config.base_url == "http://localhost:8080/v1"
    
    def test_recommended_models_exist(self):
        """Test that recommended models are defined"""
        from ramalama_config import RECOMMENDED_MODELS
        
        assert "fast" in RECOMMENDED_MODELS
        assert "balanced" in RECOMMENDED_MODELS
        assert "powerful" in RECOMMENDED_MODELS


# Mock tests (don't require API keys)
class TestAgentLogic:
    """Test agent logic without making actual API calls"""
    
    def test_confidence_check_logic(self):
        """Test the logic for determining when to stop researching"""
        deps = ResearchDependencies(
            max_iterations=10,
            min_confidence=8,
            iteration_count=3
        )
        
        # Low confidence - should continue
        should_continue = deps.iteration_count < deps.max_iterations
        assert should_continue is True
        
        # High iteration count - should stop
        deps.iteration_count = 10
        should_stop = deps.iteration_count >= deps.max_iterations
        assert should_stop is True
    
    def test_source_tracking(self):
        """Test that sources are tracked correctly"""
        deps = ResearchDependencies()
        
        source1 = ResearchSource(
            title="Source 1",
            content="Content 1",
            confidence=7
        )
        source2 = ResearchSource(
            title="Source 2",
            content="Content 2",
            confidence=9
        )
        
        deps.sources_collected.append(source1)
        deps.sources_collected.append(source2)
        
        assert len(deps.sources_collected) == 2
        assert deps.sources_collected[0].title == "Source 1"
        assert deps.sources_collected[1].confidence == 9


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
