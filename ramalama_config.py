"""
Configuration for using RamaLama with the Research Agent
"""
import subprocess
import json
from typing import Optional


class RamaLamaConfig:
    """Configuration helper for running models with RamaLama"""
    
    def __init__(self, model_name: str = "granite", port: int = 8080):
        self.model_name = model_name
        self.port = port
        self.base_url = f"http://localhost:{port}/v1"
    
    def serve(self, detached: bool = True) -> str:
        """
        Start serving a model with RamaLama
        
        Args:
            detached: Run in background if True
            
        Returns:
            Container/process ID
        """
        cmd = [
            "ramalama",
            "serve",
            "--port", str(self.port),
            "--name", f"research-agent-{self.model_name}"
        ]
        
        if detached:
            cmd.append("-d")
        
        cmd.append(self.model_name)
        
        print(f"Starting RamaLama model: {self.model_name} on port {self.port}")
        print(f"Command: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"Failed to start RamaLama: {result.stderr}")
        
        container_id = result.stdout.strip()
        print(f"Model started: {container_id}")
        print(f"API available at: {self.base_url}")
        
        return container_id
    
    def stop(self, container_name: Optional[str] = None):
        """Stop the RamaLama service"""
        if container_name is None:
            container_name = f"research-agent-{self.model_name}"
        
        cmd = ["ramalama", "stop", container_name]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Warning: Failed to stop {container_name}: {result.stderr}")
        else:
            print(f"Stopped: {container_name}")
    
    def list_running(self):
        """List running RamaLama models"""
        cmd = ["ramalama", "ps"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(result.stdout)
    
    def list_available(self):
        """List available models"""
        cmd = ["ramalama", "list"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(result.stdout)


# Recommended models for research tasks
RECOMMENDED_MODELS = {
    "fast": {
        "name": "granite",
        "description": "Fast, lightweight model good for quick research",
        "size": "~2GB"
    },
    "balanced": {
        "name": "granite-code:20b",
        "description": "Balanced performance for technical research",
        "size": "~12GB"
    },
    "powerful": {
        "name": "deepseek",
        "description": "Powerful model for complex reasoning",
        "size": "~20GB+"
    }
}


def print_model_recommendations():
    """Print recommended models for different use cases"""
    print("\n" + "="*80)
    print("RECOMMENDED MODELS FOR RESEARCH AGENT")
    print("="*80)
    for tier, info in RECOMMENDED_MODELS.items():
        print(f"\n{tier.upper()}:")
        print(f"  Model: {info['name']}")
        print(f"  Description: {info['description']}")
        print(f"  Size: {info['size']}")
    print("\n" + "="*80)


if __name__ == "__main__":
    print_model_recommendations()
    
    print("\nTo use with RamaLama:")
    print("1. Pull a model: ramalama pull granite")
    print("2. Run the research agent with: python research_agent_example.py --use-ramalama")
