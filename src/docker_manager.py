import docker
import os
import shutil

class DockerManager:
    def __init__(self, image_name="mcp-agent-runner", dockerfile_path="."):
        try:
            self.client = docker.from_env()
        except Exception as e:
            self.client = None
            print(f"Warning: Docker client could not be initialized: {e}")
            
        self.image_name = image_name
        self.dockerfile_path = dockerfile_path

    def check_docker(self):
        if not self.client:
            return False
        try:
            self.client.ping()
            return True
        except Exception:
            return False


    def build_image(self):
        print(f"Building Docker image {self.image_name}...")
        try:
            self.client.images.build(
                path=self.dockerfile_path,
                tag=self.image_name,
                dockerfile="Dockerfile.agent"
            )
            print("Image build successful.")
        except docker.errors.BuildError as e:
            print(f"Error building image: {e}")
            raise

    def run_tests(self, repo_path, command="./gradlew test"):
        abs_repo_path = os.path.abspath(repo_path)
        print(f"Running tests in {abs_repo_path} using {self.image_name}...")
        
        try:
            container = self.client.containers.run(
                self.image_name,
                command=command,
                volumes={abs_repo_path: {'bind': '/workspace', 'mode': 'rw'}},
                working_dir="/workspace",
                detach=True,
                remove=False # We might want to keep it to inspect logs if it crashes hard, but ideally remove=True. Let's keep False for debugging.
            )
            
            result = container.wait()
            logs = container.logs().decode('utf-8')
            container.remove()
            
            print(f"Test run finished with exit code: {result['StatusCode']}")
            return {
                "exit_code": result['StatusCode'],
                "logs": logs,
                "artifacts_path": os.path.join(abs_repo_path, "build/test-results/test")
            }
        except docker.errors.ContainerError as e:
            print(f"Container error: {e}")
            raise
        except Exception as e:
            print(f"Error running container: {e}")
            raise

if __name__ == "__main__":
    # Test harness
    dm = DockerManager()
    dm.build_image()
    # Assuming we are running this from project root and example repo is there
    # dm.run_tests("modular-api-automation-framework")
