import os
import re
import subprocess
from github import Github, GithubException
from dotenv import load_dotenv

load_dotenv()

class GitHubManager:
    """
    Manages GitHub operations for the self-healing agent:
    - Extract repository info from Git remote
    - Create feature branches
    - Push branches to GitHub
    - Create Pull Requests
    """
    
    def __init__(self, repo_path, token=None):
        self.repo_path = os.path.abspath(repo_path)
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.github = Github(self.token) if self.token else None
        self.owner, self.repo_name = self._extract_repo_info()
        self.repo = None
        
        if self.github and self.owner and self.repo_name:
            try:
                self.repo = self.github.get_repo(f"{self.owner}/{self.repo_name}")
            except GithubException as e:
                print(f"Warning: Could not access GitHub repo: {e}")
    
    def _extract_repo_info(self):
        """
        Extract owner and repo name from Git remote URL.
        Supports both HTTPS and SSH formats:
        - https://github.com/owner/repo.git
        - git@github.com:owner/repo.git
        """
        try:
            result = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            remote_url = result.stdout.strip()
            
            # Parse HTTPS format
            https_match = re.match(r'https://github\.com/([^/]+)/(.+?)(?:\.git)?$', remote_url)
            if https_match:
                return https_match.group(1), https_match.group(2)
            
            # Parse SSH format
            ssh_match = re.match(r'git@github\.com:([^/]+)/(.+?)(?:\.git)?$', remote_url)
            if ssh_match:
                return ssh_match.group(1), ssh_match.group(2)
            
            print(f"Could not parse GitHub URL: {remote_url}")
            return None, None
            
        except subprocess.CalledProcessError:
            print("Could not get Git remote URL")
            return None, None
    
    def get_current_branch(self):
        """Get the current Git branch name."""
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None
    
    def create_branch(self, branch_name, base_branch="master"):
        """
        Create a new Git branch from base_branch.
        
        Args:
            branch_name: Name of the new branch
            base_branch: Base branch to create from (default: master)
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Ensure we're on the base branch
            subprocess.run(
                ["git", "checkout", base_branch],
                cwd=self.repo_path,
                capture_output=True,
                check=True
            )
            
            # Pull latest changes
            subprocess.run(
                ["git", "pull", "origin", base_branch],
                cwd=self.repo_path,
                capture_output=True,
                check=True
            )
            
            # Create and checkout new branch
            subprocess.run(
                ["git", "checkout", "-b", branch_name],
                cwd=self.repo_path,
                capture_output=True,
                check=True
            )
            
            print(f"✓ Created branch: {branch_name}")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to create branch: {e}")
            return False
    
    def push_branch(self, branch_name):
        """
        Push branch to GitHub remote.
        
        Args:
            branch_name: Name of the branch to push
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            subprocess.run(
                ["git", "push", "-u", "origin", branch_name],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            print(f"✓ Pushed branch to GitHub: {branch_name}")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to push branch: {e.stderr}")
            return False
    
    def create_pull_request(self, branch_name, title, body, labels=None, base_branch="master"):
        """
        Create a Pull Request on GitHub.
        
        Args:
            branch_name: Source branch for the PR
            title: PR title
            body: PR description (markdown)
            labels: List of label names to add
            base_branch: Target branch for the PR (default: master)
        
        Returns:
            str: PR URL if successful, None otherwise
        """
        if not self.repo:
            print("✗ GitHub repository not accessible. Cannot create PR.")
            return None
        
        try:
            # Create the PR
            pr = self.repo.create_pull(
                title=title,
                body=body,
                head=branch_name,
                base=base_branch
            )
            
            # Add labels if provided
            if labels:
                try:
                    pr.add_to_labels(*labels)
                except GithubException as e:
                    print(f"Warning: Could not add labels: {e}")
            
            print(f"✓ Pull Request created: {pr.html_url}")
            return pr.html_url
            
        except GithubException as e:
            print(f"✗ Failed to create PR: {e}")
            return None
    
    def generate_pr_body(self, failure_context, fix_suggestion):
        """
        Generate a detailed PR description.
        
        Args:
            failure_context: FailureContext object
            fix_suggestion: FixSuggestion object
        
        Returns:
            str: Markdown-formatted PR body
        """
        return f"""## 🤖 Automated Self-Healing Fix

### Issue Detected
- **Test:** `{failure_context.test_class}#{failure_context.test_name}`
- **Failure Type:** `{failure_context.failure_type}`
- **Error Message:**
  ```
  {failure_context.message}
  ```

### Fix Applied
{fix_suggestion.explanation}

### Confidence Score
**{fix_suggestion.confidence:.1%}** - AI-generated fix confidence

### Changes
```diff
{fix_suggestion.diff}
```

---
*This PR was automatically generated by the [Self-Healing MCP Agent](https://github.com/{self.owner}/{self.repo_name})*  
*Powered by Google Gemini 2.0 Flash ✨*
"""
