import os
import subprocess
import re

class PatchApplier:
    def __init__(self, repo_path):
        self.repo_path = os.path.abspath(repo_path)

    def apply_patch(self, patch_content):
        """
        Apply a patch with multiple strategies:
        1. Try git apply (for complex multi-file patches)
        2. Fall back to direct file replacement (for simple single-file fixes)
        """
        # Clean the patch: remove markdown blocks if present
        if "```diff" in patch_content:
            patch_content = patch_content.split("```diff")[1].split("```")[0]
        elif "```" in patch_content:
            patch_content = patch_content.split("```")[1].split("```")[0]
        
        patch_content = patch_content.strip()
        
        # Normalize paths: Docker uses /workspace, host uses actual repo path
        patch_content = self._normalize_paths(patch_content)
        
        # Create a clean Git snapshot (only source files, not build artifacts)
        self._create_clean_snapshot()
        
        # Strategy 1: Try git apply first
        if self._try_git_apply(patch_content):
            print("✓ Patch applied successfully via git apply.")
            return True
        
        # Strategy 2: Fall back to direct file replacement for simple fixes
        print("Falling back to direct application...")
        if self._try_direct_replacement(patch_content):
            print("✓ Patch applied successfully via direct replacement.")
            return True
        
        print("✗ All patch strategies failed.")
        return False

    def _normalize_paths(self, patch_content):
        """
        Normalize paths in patch to handle Docker /workspace vs host paths.
        Also handles both 'a/' and 'b/' prefixes in diff format.
        """
        # Replace /workspace with empty string (relative paths)
        normalized = patch_content.replace("/workspace/", "")
        return normalized

    def _create_clean_snapshot(self):
        """
        Create a Git commit with ONLY source files, excluding build artifacts.
        This prevents "lacks the necessary blob" errors.
        """
        try:
            # Only add source directories (not build/, .gradle/, etc.)
            source_dirs = ["src/", "gradle/", "*.gradle", "*.xml", "*.yml", "*.yaml", "*.properties"]
            
            for pattern in source_dirs:
                subprocess.run(
                    ["git", "add", pattern], 
                    cwd=self.repo_path, 
                    capture_output=True
                )
            
            # Commit only if there are changes
            result = subprocess.run(
                ["git", "commit", "-m", "Pre-patch snapshot (auto-generated)"], 
                cwd=self.repo_path, 
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print("Created clean Git snapshot (source files only)")
                
        except subprocess.CalledProcessError:
            pass  # It's okay if there's nothing to commit

    def _try_git_apply(self, patch_content):
        """
        Try to apply patch using git apply with tolerant flags.
        """
        patch_file = os.path.join(self.repo_path, "temp_fix.patch")
        try:
            with open(patch_file, "w") as f:
                f.write(patch_content + "\n")
            
            # Try git apply with 3-way merge
            cmd = [
                "git", "apply", 
                "--whitespace=fix", 
                "--3way", 
                "--ignore-space-change", 
                "--ignore-whitespace",
                "temp_fix.patch"
            ]
            result = subprocess.run(
                cmd, 
                cwd=self.repo_path, 
                capture_output=True, 
                text=True
            )
            
            if result.returncode == 0:
                return True
            
            print(f"git apply failed: {result.stderr.strip()}")
            return False
            
        except Exception as e:
            print(f"Error in git apply: {e}")
            return False
        finally:
            if os.path.exists(patch_file):
                os.remove(patch_file)

    def _try_direct_replacement(self, patch_content):
        """
        For simple single-file patches, directly apply the changes.
        Parses the diff and applies line-by-line changes.
        """
        try:
            # Parse the diff to extract file path and changes
            file_info = self._parse_diff(patch_content)
            
            if not file_info:
                print("Could not parse diff for direct replacement")
                return False
            
            file_path = os.path.join(self.repo_path, file_info['path'])
            
            if not os.path.exists(file_path):
                print(f"File not found: {file_path}")
                return False
            
            # Read current file content
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            # Apply changes
            for change in file_info['changes']:
                old_line = change['old']
                new_line = change['new']
                
                # Find and replace the line
                for i, line in enumerate(lines):
                    if line.rstrip() == old_line.rstrip():
                        lines[i] = new_line + '\n' if not new_line.endswith('\n') else new_line
                        break
            
            # Write back
            with open(file_path, 'w') as f:
                f.writelines(lines)
            
            return True
            
        except Exception as e:
            print(f"Error in direct replacement: {e}")
            return False

    def _parse_diff(self, patch_content):
        """
        Parse a unified diff to extract file path and line changes.
        Returns dict with 'path' and 'changes' (list of old/new line pairs).
        """
        try:
            lines = patch_content.split('\n')
            
            # Find file path (from +++ b/path/to/file)
            file_path = None
            for line in lines:
                if line.startswith('+++ b/'):
                    file_path = line[6:].strip()
                    break
                elif line.startswith('+++ '):
                    # Handle cases without b/ prefix
                    file_path = line[4:].strip()
                    break
            
            if not file_path:
                return None
            
            # Extract changes (lines starting with - and +)
            changes = []
            i = 0
            while i < len(lines):
                line = lines[i]
                if line.startswith('-') and not line.startswith('---'):
                    old_line = line[1:]  # Remove '-' prefix
                    # Look for corresponding + line
                    if i + 1 < len(lines) and lines[i + 1].startswith('+') and not lines[i + 1].startswith('+++'):
                        new_line = lines[i + 1][1:]  # Remove '+' prefix
                        changes.append({'old': old_line, 'new': new_line})
                        i += 2
                        continue
                i += 1
            
            return {
                'path': file_path,
                'changes': changes
            }
            
        except Exception as e:
            print(f"Error parsing diff: {e}")
            return None

    def revert_changes(self):
        """
        Hard reset to HEAD to clean workspace.
        """
        subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=self.repo_path)
        print("Reverted all changes to HEAD")
