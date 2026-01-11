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

        # Smart Resolve: Fix incorrect paths from LLM (e.g. missing src/test/java)
        patch_content = self._smart_resolve_paths(patch_content)
        
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

    def _smart_resolve_paths(self, patch_content):
        """
        Scans the patch for file paths. If the path specified doesn't exist,
        searches the repository for a file with the same name and updates the patch.
        """
        lines = patch_content.split('\n')
        new_lines = []
        
        for line in lines:
            # Handle standard git diff headers
            if line.startswith('--- a/') or line.startswith('+++ b/'):
                prefix = line[:6]
                path = line[6:].strip()
                
                # Check if this path exists relative to repo
                abs_path = os.path.join(self.repo_path, path)
                if not os.path.exists(abs_path):
                    # It doesn't exist. Let's find the real file.
                    filename = os.path.basename(path)
                    real_path = self._find_file_recursive(filename)
                    
                    if real_path:
                        # Found it! Calculate relative path
                        rel_path = os.path.relpath(real_path, self.repo_path)
                        # Update the line with the correct path
                        new_lines.append(f"{prefix}{rel_path}")
                        # Only print if we actually changed something meaningful
                        if path != rel_path:
                            print(f"Fixed patch path: {path} -> {rel_path}")
                        continue
            
            new_lines.append(line)
        
        return '\n'.join(new_lines)

    def _find_file_recursive(self, filename):
        """
        Search for a file by name recursively in the repository.
        Ignores common build/artifact directories.
        """
        for root, dirs, files in os.walk(self.repo_path):
            # optimization: skip .git, build, etc.
            if '.git' in dirs: dirs.remove('.git')
            if 'build' in dirs: dirs.remove('build')
            if '.gradle' in dirs: dirs.remove('.gradle')
            if 'target' in dirs: dirs.remove('target')
            
            if filename in files:
                return os.path.join(root, filename)
        return None

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

    def _lines_match(self, line1, line2):
        """
        Fuzzy match two lines, handling:
        1. Exact match (stripped)
        2. Whitespace differences
        3. Numeric format differences (e.g. 01 vs 1 in Java)
        """
        # 1. Exact match (stripped)
        if line1.strip() == line2.strip():
            return True
        
        # 2. Ignore whitespace
        if "".join(line1.split()) == "".join(line2.split()):
            return True
            
        # 3. Fuzzy number match (handle 01 vs 1, etc)
        # This is critical for Java 01 vs 1 type mismatches from LLM hallucinations
        def normalize_nums(s):
             # Replace 01 -> 1, but keep 0. 
             # Regex: look for word boundary or non-digit, then 0+, then digit+
             return re.sub(r'(?<!\d)0+(\d+)', r'\1', s)
        
        s1 = normalize_nums(line1.strip())
        s2 = normalize_nums(line2.strip())
        
        # Check again after normalization (and space stripping)
        if "".join(s1.split()) == "".join(s2.split()):
            return True
            
        return False

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
            
            # Try to resolve path if it doesn't exist (using the smart resolver logic essentially)
            file_path = os.path.join(self.repo_path, file_info['path'])
            if not os.path.exists(file_path):
                # Try finding it by name
                found = self._find_file_recursive(os.path.basename(file_info['path']))
                if found:
                    file_path = found
                else:
                    print(f"File not found: {file_path}")
                    return False
            
            # Read current file content
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            # Apply changes
            changes_made = False
            for change in file_info['changes']:
                old_line = change['old']
                new_line = change['new']
                
                # Find and replace the line
                # We normalize whitespace for comparison to be more robust
                replaced = False
                for i, line in enumerate(lines):
                    if self._lines_match(line, old_line):
                        # Preserve indentation of the new line if possible on direct replacement
                        # But typically the new line from diff has its own whitespace.
                        # We'll just trust the diff for now.
                        lines[i] = new_line + '\n' if not new_line.endswith('\n') else new_line
                        replaced = True
                        changes_made = True
                        break
                
                if not replaced:
                    print(f"Warning: Could not find line to replace: '{old_line.strip()}'")
            
            if not changes_made:
                print("No changes were applied to the file.")
                return False

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
                elif line.startswith('--- a/'):
                     # Fallback to --- if +++ is missing or weird
                     file_path = line[6:].strip()
            
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
