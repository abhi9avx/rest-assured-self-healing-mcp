import argparse
import sys
import os
import subprocess
import time
import re
from src.config_loader import ConfigLoader
from src.docker_manager import DockerManager
from src.failure_analyzer import FailureAnalyzer
from src.gemini_client import GeminiClient
from src.patch_applier import PatchApplier
from src.github_manager import GitHubManager
from src.security_utils import SecurityUtils

class Term:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

    @staticmethod
    def header(msg):
        print(f"\n{Term.HEADER}{Term.BOLD}=== {msg} ==={Term.ENDC}")

    @staticmethod
    def section(msg):
        print(f"\n{Term.CYAN}➜ {msg}{Term.ENDC}")

    @staticmethod
    def info(msg):
        print(f"{Term.BLUE}ℹ {msg}{Term.ENDC}")

    @staticmethod
    def success(msg):
        print(f"{Term.GREEN}✓ {msg}{Term.ENDC}")

    @staticmethod
    def error(msg):
        print(f"{Term.FAIL}✗ {msg}{Term.ENDC}")

    @staticmethod
    def warning(msg):
        print(f"{Term.WARNING}⚠ {msg}{Term.ENDC}")
        
    @staticmethod
    def print_logs(logs):
        print(f"{Term.WARNING}┌──────────────── CONSOLE LOGS ────────────────┐{Term.ENDC}")
        # Print a limited amount to avoid clutter
        lines = logs.strip().split('\n')[-20:] # Only show last 20 lines by default
        for line in lines:
            print(f"│ {line}")
        print(f"{Term.WARNING}└──────────────────────────────────────────────┘{Term.ENDC}")


def main():
    parser = argparse.ArgumentParser(description="MCP Self-Healing Agent")
    parser.add_argument("--repo", required=True, help="Path to the repository to heal")
    parser.add_argument("--config", default="config.yml", help="Path to config file")
    parser.add_argument("--no-docker-build", action="store_true", help="Skip docker build")
    parser.add_argument("--test-filter", help="Specific test class or method to run (e.g., GetUserApiTest)")
    
    args = parser.parse_args()

    # 1. Load Config
    Term.header("Phase 1: Config Loading")
    config = ConfigLoader(args.config).load_config()
    max_attempts = config.get("max_attempts", 3)
    Term.success("Configuration loaded")

    # 2. Setup Docker
    Term.header("Phase 2: Docker Setup")
    dm = DockerManager()
    if not dm.check_docker():
        Term.error("CRITICAL ERROR: Docker is not running or not working.")
        sys.exit(1)

    if not args.no_docker_build:
        Term.section("Building Docker Environment")
        dm.build_image()
        Term.success("Docker image ready")

    repo_path = args.repo
    patch_applier = PatchApplier(repo_path)
    
    # Track repair history for final report
    repair_history = []

    for attempt in range(1, max_attempts + 1):
        Term.header(f"Repair Attempt {attempt}/{max_attempts}")
        
        # 3. Run Tests
        command = "./gradlew test"
        if args.test_filter:
            Term.info(f"Applying test filter: {args.test_filter}")
            command += f" --tests {args.test_filter}"

        Term.section(f"Running Tests")
        run_result = dm.run_tests(repo_path, command=command)
        
        if run_result["exit_code"] != 0:
            Term.error(f"Tests Failed (Exit Code: {run_result['exit_code']})")
            Term.print_logs(run_result["logs"])
        else:
            Term.success("All tests passed!")

        analyzer = FailureAnalyzer(run_result["artifacts_path"])
        failures = analyzer.analyze()
        
        scripting_failures = [f for f in failures if f.is_scripting_issue]
        
        if not scripting_failures:
            Term.success("System verified. No scripting issues found.")
            break
            
        Term.warning(f"Found {len(scripting_failures)} scripting issue(s).")
        target_failure = scripting_failures[0] # Focus on first one
        Term.info(f"Targeting failure: {target_failure.test_name}")

        # 5. Get File Content
        file_content = ""
        if target_failure.file_path:
             search_name = os.path.basename(target_failure.file_path) if target_failure.file_path else f"{target_failure.test_class}.java"
             if "." not in search_name:
                 search_name += ".java"
                 
             found_path = None
             
             # Search Strategies
             if os.path.isabs(target_failure.file_path) and os.path.exists(target_failure.file_path):
                 found_path = target_failure.file_path
             if not found_path:
                 potential_path = os.path.join(repo_path, target_failure.file_path)
                 if os.path.exists(potential_path):
                     found_path = potential_path
             if not found_path:
                 common_test_dirs = ["src/test/java", "src/main/java", "test", "tests"]
                 for test_dir in common_test_dirs:
                     search_root = os.path.join(repo_path, test_dir)
                     if os.path.exists(search_root):
                         for root, dirs, files in os.walk(search_root):
                             if search_name in files:
                                 found_path = os.path.join(root, search_name)
                                 break
                     if found_path: break
             
             # Fallback Deep Search
             if not found_path:
                 Term.info(f"Performing deep search for {search_name}...")
                 for root, dirs, files in os.walk(repo_path):
                     dirs[:] = [d for d in dirs if d not in ['.git', 'node_modules', 'build', 'target', '.gradle']]
                     if search_name in files:
                         found_path = os.path.join(root, search_name)
                         break
            
             if found_path:
                 Term.info(f"Context loaded from: {found_path}")
                 try:
                     with open(found_path, "r") as f:
                         file_content = f.read()
                 except Exception as e:
                     Term.error(f"Error reading file: {e}")
             else:
                 Term.warning(f"Could not locate file for {target_failure.test_class}")

        # 5.5 Enhanced Context: Read related framework files
        Term.section("Gathering Context")
        try:
            lines = file_content.split('\n')
            for line in lines:
                if line.strip().startswith("import "):
                    parts = line.strip().split(" ")
                    if len(parts) > 1:
                        imported_class = parts[1].replace(";", "").strip()
                        rel_path_java = imported_class.replace(".", "/") + ".java"
                        
                        possible_roots = ["src/main/java", "src/test/java", "src"]
                        for root in possible_roots:
                            full_path = os.path.join(repo_path, root, rel_path_java)
                            if os.path.exists(full_path):
                                Term.info(f"Adding related file: {rel_path_java}")
                                try:
                                    with open(full_path, "r") as f:
                                        file_content += f"\n\n--- RELATED FILE: {rel_path_java} ---\n" + f.read()
                                except Exception as read_err:
                                    print(f"Failed to read {full_path}: {read_err}")
                                break
        except Exception as e:
            Term.warning(f"Context gathering warning: {e}")

        # 6. Ask Gemini
        Term.section("AI Analysis")
        Term.info("Consulting Gemini...")
        client = GeminiClient()
        recent_logs = run_result.get("logs", "")[-2000:] if "logs" in run_result else ""
        fix = client.get_fix_suggestion(target_failure, file_content, console_logs=recent_logs)
        
        if fix.confidence < config["good_confidence_threshold"]:
            Term.warning(f"Confidence too low ({fix.confidence}). Skipping.")
            break
            
        Term.success(f"Fix Proposed: {fix.explanation}")
        
        current_attempt = {
            "attempt": attempt,
            "test": target_failure.test_name,
            "explanation": fix.explanation,
            "diff": fix.diff,
            "status": "pending"
        }
        repair_history.append(current_attempt)
        
        # 7. GitHub PR Workflow (if enabled)
        github_config = config.get("github", {})
        if github_config.get("enabled", False):
            Term.header("GitHub Workflow")
            github_mgr = GitHubManager(repo_path)
            
            base_branch = github_config.get("base_branch", "master")
            branch_prefix = github_config.get("branch_prefix", "fix/self-healing")
            branch_name = f"{branch_prefix}-{target_failure.test_name.lower().replace('_', '-')}-{int(time.time())}"
            
            if not github_mgr.create_branch(branch_name, base_branch):
                Term.error("Failed to create branch. Falling back to local fix.")
            else:
                Term.info(f"Created branch: {branch_name}")
                success = patch_applier.apply_patch(fix.diff)
                if not success:
                    Term.error("Patch application failed via all strategies.")
                    current_attempt["status"] = "patch_failed"
                    patch_applier.revert_changes()
                    subprocess.run(["git", "checkout", base_branch], cwd=repo_path, capture_output=True)
                    continue
                
                Term.success("Patch applied. Verifying...")
                Term.section("Verification")
                verify_result = dm.run_tests(repo_path, command=command)
                
                if verify_result["exit_code"] != 0:
                    Term.error(f"Verification Failed (Exit Code: {verify_result['exit_code']})")
                    current_attempt["status"] = "verification_failed"
                    patch_applier.revert_changes()
                    subprocess.run(["git", "checkout", base_branch], cwd=repo_path, capture_output=True)
                    continue

                Term.success("Fix Verified! Proceeding to PR.")
                current_attempt["status"] = "success_pr_created"
                
                commit_msg = f"🤖 Fix: {target_failure.test_name}\n\n{fix.explanation}"
                subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
                subprocess.run(["git", "commit", "-m", commit_msg], cwd=repo_path, capture_output=True, check=True)
                
                if not github_mgr.push_branch(branch_name):
                    Term.error("Failed to push branch.")
                else:
                    pr_title = f"🤖 Fix: {target_failure.test_name}"
                    pr_body = github_mgr.generate_pr_body(target_failure, fix)
                    pr_labels = github_config.get("pr_labels", ["self-healing", "automated-fix"])
                    
                    pr_url = github_mgr.create_pull_request(branch_name, pr_title, pr_body, labels=pr_labels, base_branch=base_branch)
                    
                    if pr_url:
                        Term.success(f"Pull Request Created: {pr_url}")
                        break
        else:
            success = patch_applier.apply_patch(fix.diff)
            if not success:
                Term.error("Patch application failed.")
                current_attempt["status"] = "patch_failed"
                patch_applier.revert_changes()
                break
            current_attempt["status"] = "success_local_fix"
            
    else:
        Term.warning("Max attempts reached.")
    
    # Final Summary Report
    if repair_history:
        print(f"\n{Term.HEADER}{Term.BOLD}" + "="*50)
        print("🔍 SELF-HEALING DIAGNOSTIC SUMMARY")
        print("="*50 + f"{Term.ENDC}")
        for entry in repair_history:
            status_icon = "✅" if "success" in entry["status"] else "❌"
            color = Term.GREEN if "success" in entry["status"] else Term.FAIL
            print(f"\n{Term.BOLD}Attempt {entry['attempt']}: {entry['test']}{Term.ENDC}")
            print(f"Status: {color}{status_icon} {entry['status'].upper()}{Term.ENDC}")
            print(f"Proposed Fix: {entry['explanation'][:150]}..." if len(entry['explanation']) > 150 else f"Proposed Fix: {entry['explanation']}")
            
        if any("failed" in e["status"] for e in repair_history) or len(repair_history) == max_attempts:
            print(f"\n{Term.WARNING}⚠️  RECOMMENDATION:{Term.ENDC}")
            print("The agent could not fully resolve the issue. Please review the logs above.")
        print(f"{Term.HEADER}" + "="*50 + f"\n{Term.ENDC}")

if __name__ == "__main__":
    main()
