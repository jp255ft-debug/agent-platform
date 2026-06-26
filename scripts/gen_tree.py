#!/usr/bin/env python3
"""Gera a arvore limpa do projeto agent-platform."""

import os
import sys

BASE = r"c:\Source\Repos\agent-platform"

EXCLUDE_DIRS = {
    ".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache",
    "node_modules", ".vscode", "htmlcov", "out", "cache", "-p",
    ".mypy_cache", ".hypothesis", ".tox", "build", "dist",
}

EXCLUDE_FILES = {
    ".coverage", "anvil.exe", "cast.exe", "chisel.exe", "forge.exe",
    "foundry.lock", "foundry.zip", "package-lock.json",
    "contracts_src_AgentDelegation_sol_AgentDelegation.abi",
    "contracts_src_libraries_EIP712Helper_sol_EIP712Helper.abi",
    "2.0.0", "=4.1.0",
}

EXCLUDE_EXTENSIONS = {".pyc", ".pyo", ".so", ".pyd", ".exe"}

def should_exclude(name, full_path):
    if os.path.isdir(full_path):
        return name in EXCLUDE_DIRS
    if name in EXCLUDE_FILES:
        return True
    ext = os.path.splitext(name)[1]
    if ext in EXCLUDE_EXTENSIONS:
        return True
    return False

def tree(dir_path, prefix=""):
    try:
        items = sorted(os.listdir(dir_path))
    except PermissionError:
        return
    
    items = [i for i in items if not should_exclude(i, os.path.join(dir_path, i))]
    
    for i, item in enumerate(items):
        is_last = i == len(items) - 1
        current_prefix = "+-- " if is_last else "|-- "
        full_path = os.path.join(dir_path, item)
        
        print(f"{prefix}{current_prefix}{item}")
        
        if os.path.isdir(full_path):
            extension = "    " if is_last else "|   "
            tree(full_path, prefix + extension)

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    print("agent-platform/")
    tree(BASE)
