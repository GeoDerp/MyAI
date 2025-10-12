"""
Configuration for using RamaLama with the Research Agent
"""
import subprocess
import shutil
import sys
import os
from typing import Optional


class RamaLamaConfig:
    """Configuration helper for running models with RamaLama"""
    
    def __init__(self, model_name: str = "granite", port: int = 8080):
        self.model_name = model_name
        self.port = port
        # Allow overriding the RAMALAMA host (useful when agent and RamaLama
        # run in separate containers on the same user-defined network). If
        # RAMALAMA_HOST is set, use that as the hostname; otherwise default
        # to localhost.
        ramalama_host = os.environ.get("RAMALAMA_HOST", "localhost")
        self.base_url = f"http://{ramalama_host}:{port}/v1"
    
    def serve(self, detached: bool = True, host_binds: Optional[list[tuple]] = None,
              use_host_container: bool = False, container_image: Optional[str] = None) -> str:
        """
        Start serving a model with RamaLama
        
        Args:
            detached: Run in background if True
            
        Returns:
            Container/process ID
        """
        # If the caller requests starting a host container directly, construct
        # and run a podman/docker `run` command that launches the provided
        # container image and mounts host directories (host_binds) into it.
        # This allows the launched ramalama container to reference model
        # images or files that live on the host filesystem.
        if use_host_container:
            if not container_image:
                raise ValueError("container_image must be provided when use_host_container=True")

            runtime = shutil.which("podman") or shutil.which("docker") or "podman"
            name = f"research-agent-{self.model_name}"
            cmd = [runtime, "run"]
            if detached:
                cmd.append("-d")
            cmd += ["--name", name, "-p", f"{self.port}:{self.port}"]

            # Mount any host paths into the container so ramalama can access
            # model files that live outside the build image.
            if host_binds:
                for host_path, container_path in host_binds:
                    cmd += ["-v", f"{host_path}:{container_path}"]

            # Pass the model name as an env var so container entrypoints can
            # choose and serve the requested model. Consumers of this helper
            # should design container images to honor RAMALAMA_MODEL.
            cmd += ["-e", f"RAMALAMA_MODEL={self.model_name}", container_image]

            print(f"Starting host container via: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Failed to start host container: {result.stderr}")

            container_id = result.stdout.strip() or name
            print(f"Host container started: {container_id}")
            print(f"API available at: {self.base_url}")
            return container_id

        # Prefer calling the ramalama CLI if it's on PATH; otherwise invoke
        # the module with the same Python interpreter that's running this code
        # (this is more reliable inside venvs where entry points may not be on PATH).
        base_args = ["serve", "--port", str(self.port), "--name", f"research-agent-{self.model_name}"]
        if detached:
            base_args.insert(len(base_args), "-d")
        base_args.append(self.model_name)

        if shutil.which("ramalama"):
            cmd = ["ramalama"] + base_args
        else:
            cmd = [sys.executable, "-m", "ramalama"] + base_args

        print(f"Starting RamaLama model: {self.model_name} on port {self.port}")
        print(f"Command: {' '.join(cmd)}")

        # Propagate an appropriate DOCKER_HOST so ramalama (which uses container
        # runtimes) can connect to the host podman socket if it's mounted. Users
        # may also set CONTAINER_HOST (for example in a devcontainer / remote
        # environment) to point at a socket or remote daemon. If provided,
        # CONTAINER_HOST takes precedence and will be copied to DOCKER_HOST.
        env = os.environ.copy()
        container_host = env.get("CONTAINER_HOST") or env.get("CONTAINER_HOST_URL")
        if container_host:
            # Use the explicit container host value from the environment
            env.setdefault("DOCKER_HOST", container_host)
        else:
            if os.path.exists("/run/podman/podman.sock"):
                env.setdefault("DOCKER_HOST", "unix:///run/podman/podman.sock")
            elif os.path.exists("/run/user/1000/podman/podman.sock"):
                env.setdefault("DOCKER_HOST", "unix:///run/user/1000/podman/podman.sock")

        # Pre-flight: check that the expected socket (if present) is readable by
        # the current process. If the socket exists but is not accessible we
        # surface a helpful error to the user explaining how to mount it or
        # change permissions.
        # Decide which socket paths to consider for accessibility checks. If
        # CONTAINER_HOST points to a unix socket path, include that in checks so
        # we can give a useful diagnostic. Otherwise, fall back to common
        # default locations.
        socket_candidates = []
        if container_host and container_host.startswith("unix://"):
            # normalize unix:///path and unix://localhost/path variants
            sock_path = container_host[len("unix://"):]
            socket_candidates.append(sock_path)

        socket_candidates += [
            "/run/podman/podman.sock",
            "/run/user/1000/podman/podman.sock",
        ]

        accessible = False
        for s in socket_candidates:
            try:
                if os.path.exists(s) and os.access(s, os.R_OK | os.W_OK):
                    accessible = True
                    break
            except Exception:
                # os.access may raise on special files in some environments; ignore
                pass

        if not accessible and any(os.path.exists(s) for s in socket_candidates):
            raise RuntimeError(
                "Podman socket exists on the host but is not accessible inside the\n"
                "container. To allow RamaLama to spawn a secondary container you must:\n"
                "  * Mount the podman socket into the container (example):\n"
                "      --volume=/run/user/1000/podman/podman.sock:/run/user/1000/podman/podman.sock\n"
                "    and ensure the socket is readable/writable by the container UID,\n"
                "    or run the container as root (not recommended).\n"
                "  * Or set CONTAINER_HOST to point at a reachable socket or remote\n"
                "    daemon endpoint (for example in a devcontainer config):\n"
                "      \"remoteEnv\": { \"CONTAINER_HOST\": \"unix:///run/podman/podman.sock\" }\n"
                "  * Alternatively, run a RamaLama server outside this container and\n"
                "    point the agent at it via RAMALAMA_PORT/RAMALAMA_MODEL.\n"
            )

        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        
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
        
        if shutil.which("ramalama"):
            cmd = ["ramalama", "stop", container_name]
        else:
            cmd = [sys.executable, "-m", "ramalama", "stop", container_name]
        env = os.environ.copy()
        # Respect a user-provided CONTAINER_HOST (maps to DOCKER_HOST) if set
        if env.get("CONTAINER_HOST"):
            ch = env.get("CONTAINER_HOST")
            if ch:
                env.setdefault("DOCKER_HOST", ch)
        elif os.path.exists("/run/podman/podman.sock"):
            env.setdefault("DOCKER_HOST", "unix:///run/podman/podman.sock")
        elif os.path.exists("/run/user/1000/podman/podman.sock"):
            env.setdefault("DOCKER_HOST", "unix:///run/user/1000/podman/podman.sock")
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        
        if result.returncode != 0:
            print(f"Warning: Failed to stop {container_name}: {result.stderr}")
        else:
            print(f"Stopped: {container_name}")
    
    def list_running(self):
        """List running RamaLama models"""
        if shutil.which("ramalama"):
            cmd = ["ramalama", "ps"]
        else:
            cmd = [sys.executable, "-m", "ramalama", "ps"]
        env = os.environ.copy()
        if env.get("CONTAINER_HOST"):
            ch = env.get("CONTAINER_HOST")
            if ch:
                env.setdefault("DOCKER_HOST", ch)
        elif os.path.exists("/run/podman/podman.sock"):
            env.setdefault("DOCKER_HOST", "unix:///run/podman/podman.sock")
        elif os.path.exists("/run/user/1000/podman/podman.sock"):
            env.setdefault("DOCKER_HOST", "unix:///run/user/1000/podman/podman.sock")
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        print(result.stdout)
    
    def list_available(self):
        """List available models"""
        if shutil.which("ramalama"):
            cmd = ["ramalama", "list"]
        else:
            cmd = [sys.executable, "-m", "ramalama", "list"]
        env = os.environ.copy()
        if env.get("CONTAINER_HOST"):
            ch = env.get("CONTAINER_HOST")
            if ch:
                env.setdefault("DOCKER_HOST", ch)
        elif os.path.exists("/run/podman/podman.sock"):
            env.setdefault("DOCKER_HOST", "unix:///run/podman/podman.sock")
        elif os.path.exists("/run/user/1000/podman/podman.sock"):
            env.setdefault("DOCKER_HOST", "unix:///run/user/1000/podman/podman.sock")
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
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

    print("\nNote on spawning host containers from inside the agent:")
    print("If you want the agent to spawn a host-side container (podman/docker) and\n"
          "have that container access host model files, mount the host container\n"
          "socket into this container or set the CONTAINER_HOST environment variable.\n"
          "Example devcontainer/remote config snippet:\n"
          "  \"remoteEnv\": {\n"
          "    \"CONTAINER_HOST\": \"unix:///run/podman/podman.sock\"\n"
          "  }\n"
          "Or start the container with a volume mount (example):\n"
          "  --volume=/run/user/1000/podman/podman.sock:/run/user/1000/podman/podman.sock\n")
