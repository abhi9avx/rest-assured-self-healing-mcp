import argparse
import sys
import os
from src.config_loader import ConfigLoader
from src.docker_manager import DockerManager
from src.failure_analyzer import FailureAnalyzer
from src.gemini_client import GeminiClient
from src.patch_applier import PatchApplier
from src.github_manager import GitHubManager
from src.security_utils import SecurityUtils

def main():
    parser = argparse.ArgumentParser(description="MCP Self-Healing Agent")
    parser.add_argument("--repo", required=True, help="Path to the repository to heal")
    parser.add_argument("--config", default="config.yml", help="Path to config file")
    parser.add_argument("--no-docker-build", action="store_true", help="Skip docker build")
    parser.add_argument("--test-filter", help="Specific test class or method to run (e.g., GetUserApiTest)")
    
    args = parser.parse_args()

    # 1. Load Config
    print("--- Phase 1: Config Loading ---")
    config = ConfigLoader(args.config).load_config()
    max_attempts = config.get("max_attempts", 3)

    # 2. Setup Docker
    print("--- Phase 2: Docker Setup ---")
    dm = DockerManager()
    if not dm.check_docker():
        print("CRITICAL ERROR: Docker is not running or not working. Please start Docker Desktop/Daemon.")
        sys.exit(1)

    if not args.no_docker_build:
        dm.build_image()

    repo_path = args.repo
    patch_applier = PatchApplier(repo_path)

    for attempt in range(1, max_attempts + 1):
        print(f"\n=== Attempt {attempt}/{max_attempts} ===")
        
        # 3. Run Tests
        command = "./gradlew test"
        if args.test_filter:
            print(f"Applying test filter: {args.test_filter}")
            command += f" --tests {args.test_filter}"

        print(f"Running tests in container: {command}")
        run_result = dm.run_tests(repo_path, command=command)
        
        if run_result["exit_code"] != 0:
            print("Test run failed (Exit Code: {}). Logs:".format(run_result["exit_code"]))
            SecurityUtils.safe_print(run_result["logs"][-2000:]) # Print last 2000 chars of logs

        analyzer = FailureAnalyzer(run_result["artifacts_path"])
        failures = analyzer.analyze()
        
        scripting_failures = [f for f in failures if f.is_scripting_issue]
        
        if not scripting_failures:
            print("No scripting issues detected. Stopping.")
            break
            
        print(f"Found {len(scripting_failures)} scripting issues.")
        target_failure = scripting_failures[0] # Focus on first one
        print(f"Targeting failure: {target_failure.test_name}")

        # 5. Get File Content
        file_content = ""
        if target_failure.file_path:
             # Enhanced file discovery for complex enterprise frameworks
             # Try multiple strategies to find the file
             search_name = os.path.basename(target_failure.file_path) if target_failure.file_path else f"{target_failure.test_class}.java"
             if "." not in search_name:
                 search_name += ".java"
                 
             found_path = None
             
             # Strategy 1: Direct path if it exists
             if os.path.isabs(target_failure.file_path) and os.path.exists(target_failure.file_path):
                 found_path = target_failure.file_path
             
             # Strategy 2: Relative to repo root
             if not found_path:
                 potential_path = os.path.join(repo_path, target_failure.file_path)
                 if os.path.exists(potential_path):
                     found_path = potential_path
             
             # Strategy 3: Search in common test directories
             if not found_path:
                 common_test_dirs = [
                     "src/test/java",
                     "src/main/java",
                     "test",
                     "tests"
                 ]
                 for test_dir in common_test_dirs:
                     search_root = os.path.join(repo_path, test_dir)
                     if os.path.exists(search_root):
                         for root, dirs, files in os.walk(search_root):
                             if search_name in files:
                                 found_path = os.path.join(root, search_name)
                                 break
                     if found_path:
                         break
             
             # Strategy 4: Full repository walk (fallback for complex structures)
             if not found_path:
                 print(f"Performing deep search for {search_name}...")
                 for root, dirs, files in os.walk(repo_path):
                     # Skip common non-source directories for performance
                     dirs[:] = [d for d in dirs if d not in ['.git', 'node_modules', 'build', 'target', '.gradle']]
                     if search_name in files:
                         found_path = os.path.join(root, search_name)
                         break
            
             if found_path:
                 print(f"Read failure context from: {found_path}")
                 try:
                     with open(found_path, "r") as f:
                         file_content = f.read()
                 except Exception as e:
                     print(f"Error reading file: {e}")
             else:
                 print(f"Could not locate file for {target_failure.test_class}")
                 print(f"Searched for: {search_name}")



        # 6. Ask Gemini
        print("Consulting Gemini...")
        client = GeminiClient()
        fix = client.get_fix_suggestion(target_failure, file_content)
        
        if fix.confidence < config["good_confidence_threshold"]:
            print(f"Confidence too low ({fix.confidence}). Skipping.")
            break
            
        print(f"Applying fix: {fix.explanation}")
        
        # 7. GitHub PR Workflow (if enabled)
        github_config = config.get("github", {})
        if github_config.get("enabled", False):
            print("\n--- GitHub PR Workflow Enabled ---")
            github_mgr = GitHubManager(repo_path)
            
            # Create feature branch
            base_branch = github_config.get("base_branch", "master")
            branch_prefix = github_config.get("branch_prefix", "fix/self-healing")
            branch_name = f"{branch_prefix}-{target_failure.test_name.lower().replace('_', '-')}"
            
            if not github_mgr.create_branch(branch_name, base_branch):
                print("Failed to create branch. Falling back to local fix.")
            else:
                # Apply patch to the new branch
                success = patch_applier.apply_patch(fix.diff)
                if not success:
                    print("Patch application failed. Reverting and stopping.")
                    patch_applier.revert_changes()
                    break
                
                # Commit the fix
                commit_msg = f"🤖 Fix: {target_failure.test_name}\n\n{fix.explanation}"
                subprocess.run(
                    ["git", "commit", "-am", commit_msg],
                    cwd=repo_path,
                    capture_output=True
                )
                
                # Push to GitHub
                if not github_mgr.push_branch(branch_name):
                    print("Failed to push branch. Fix applied locally.")
                else:
                    # Create Pull Request
                    pr_title = f"🤖 Fix: {target_failure.test_name}"
                    pr_body = github_mgr.generate_pr_body(target_failure, fix)
                    pr_labels = github_config.get("pr_labels", ["self-healing", "automated-fix"])
                    
                    pr_url = github_mgr.create_pull_request(
                        branch_name=branch_name,
                        title=pr_title,
                        body=pr_body,
                        labels=pr_labels,
                        base_branch=base_branch
                    )
                    
                    if pr_url:
                        print(f"\n✅ SUCCESS! Pull Request created: {pr_url}")
                        print("The fix has been submitted for review.")
                        break  # Stop after successful PR creation
        else:
            # Original workflow: local fix only
            success = patch_applier.apply_patch(fix.diff)
            if not success:
                print("Patch application failed. Reverting and stopping.")
                patch_applier.revert_changes()
                break
            
    else:
        print("Max attempts reached.")

if __name__ == "__main__":
    main()
