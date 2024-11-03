#!/usr/bin/env python3
import os
from pathlib import Path

# Make pre-commit executable and symlink to .git/hooks
pre_commit = Path('scripts/pre_commit.py')
pre_commit.chmod(0o755)

hooks_dir = Path('.git/hooks')
hooks_dir.mkdir(exist_ok=True)

hook_path = hooks_dir / 'pre-commit'
if hook_path.exists():
    hook_path.unlink()

os.symlink(os.path.abspath(pre_commit), hook_path)
print(f'Installed pre-commit hook to {hook_path}')
