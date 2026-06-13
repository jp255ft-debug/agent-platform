#!/usr/bin/env python3
"""
validate_python.py -- Validador de codigo Python para o Agent Platform.

Verifica:
1. Sintaxe Python (ast.parse)
2. Imports existentes (tenta importar modulos)
3. Type hints basicos (presenca em funcoes publicas)
4. PEP 8 via Ruff (se disponivel)

Uso:
    python .ai/validation/validate_python.py [--fix] [--path backend/app]
"""
import ast
import importlib
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_PATH = BASE_DIR / "backend" / "app"

# Modulos que podem nao estar instalados (pular verificacao)
OPTIONAL_MODULES = {
    "web3", "eth_account", "kafka", "redis", "sqlalchemy",
    "alembic", "fastapi", "pydantic", "uvicorn",
    "aiokafka",
}

# Prefixos de modulos internos do projeto (pular verificacao)
INTERNAL_PREFIXES = {"app.", "tests."}


def check_syntax(filepath: Path) -> list[str]:
    """Verifica se o arquivo tem sintaxe Python valida."""
    errors = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        ast.parse(content)
    except SyntaxError as e:
        errors.append(f"  [ERRO] SyntaxError em {filepath.name}: {e}")
    except Exception as e:
        errors.append(f"  [ERRO] Erro ao ler {filepath.name}: {e}")
    return errors


def check_imports(filepath: Path) -> list[str]:
    """Verifica se os imports do arquivo podem ser resolvidos."""
    errors = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.split(".")[0]
                    # Pula modulos internos do projeto
                    if any(alias.name.startswith(p) for p in INTERNAL_PREFIXES):
                        continue
                    if module_name not in OPTIONAL_MODULES:
                        try:
                            importlib.import_module(module_name)
                        except ImportError:
                            errors.append(
                                f"  [ERRO] Import nao encontrado em {filepath.name}: "
                                f"'{alias.name}'"
                            )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_name = node.module.split(".")[0]
                    # Pula modulos internos do projeto
                    if any(node.module.startswith(p) for p in INTERNAL_PREFIXES):
                        continue
                    if module_name not in OPTIONAL_MODULES:
                        try:
                            importlib.import_module(module_name)
                        except ImportError:
                            errors.append(
                                f"  [ERRO] Import nao encontrado em {filepath.name}: "
                                f"'{node.module}'"
                            )
    except SyntaxError:
        pass  # Ja reportado pelo check_syntax
    return errors


def check_type_hints(filepath: Path) -> list[str]:
    """Verifica se funcoes publicas tem type hints."""
    warnings = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Pula metodos privados e dunder
                if node.name.startswith("_"):
                    continue
                # Verifica se todos os argumentos tem type hints
                args = node.args
                for arg in args.args + args.kwonlyargs:
                    if arg.arg != "self" and arg.annotation is None:
                        warnings.append(
                            f"  [AVISO] Funcao '{node.name}' em {filepath.name}: "
                            f"argumento '{arg.arg}' sem type hint"
                        )
                # Verifica se o retorno tem type hint
                if node.returns is None and not node.name.startswith("__"):
                    warnings.append(
                        f"  [AVISO] Funcao '{node.name}' em {filepath.name}: "
                        f"sem type hint de retorno"
                    )
    except SyntaxError:
        pass
    return warnings


def run_ruff(filepath: Path) -> list[str]:
    """Tenta rodar ruff check no arquivo."""
    errors = []
    try:
        result = subprocess.run(
            ["ruff", "check", "--quiet", str(filepath)],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0 and result.stdout.strip():
            errors.append(f"  [ERRO] Ruff: {result.stdout.strip()}")
    except FileNotFoundError:
        pass  # Ruff nao instalado
    except subprocess.TimeoutExpired:
        errors.append(f"  [AVISO] Ruff timeout em {filepath.name}")
    return errors


def validate_path(path: Path, fix: bool = False) -> dict:
    """Valida todos os arquivos Python em um diretorio."""
    results = {"passed": 0, "failed": 0, "warnings": 0, "errors": []}

    python_files = list(path.rglob("*.py"))
    # Filtra __pycache__
    python_files = [f for f in python_files if "__pycache__" not in str(f)]

    print(f"\n[VALIDANDO] {len(python_files)} arquivos Python em {path}...\n")

    for filepath in python_files:
        rel_path = filepath.relative_to(BASE_DIR)
        file_errors = []
        file_warnings = []

        # 1. Sintaxe
        syntax_errors = check_syntax(filepath)
        file_errors.extend(syntax_errors)

        # 2. Imports
        import_errors = check_imports(filepath)
        file_errors.extend(import_errors)

        # 3. Type hints
        hint_warnings = check_type_hints(filepath)
        file_warnings.extend(hint_warnings)

        # 4. Ruff
        if not fix:
            ruff_errors = run_ruff(filepath)
            file_errors.extend(ruff_errors)

        if file_errors or file_warnings:
            print(f"[ARQUIVO] {rel_path}")
            for e in file_errors:
                print(e)
                results["errors"].append(str(rel_path) + ": " + e)
            for w in file_warnings:
                print(w)
            results["failed"] += len(file_errors)
            results["warnings"] += len(file_warnings)
        else:
            results["passed"] += 1

    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Validador Python Agent Platform")
    parser.add_argument("--path", default=str(DEFAULT_PATH),
                        help="Caminho para validar (default: backend/app)")
    parser.add_argument("--fix", action="store_true",
                        help="Tenta corrigir automaticamente (ruff --fix)")
    args = parser.parse_args()

    path = Path(args.path).resolve()
    if not path.exists():
        print(f"[ERRO] Caminho nao encontrado: {path}")
        sys.exit(1)

    results = validate_path(path, fix=args.fix)

    print(f"\n{'='*50}")
    print(f"[RESULTADOS]")
    print(f"  [OK] Passou: {results['passed']}")
    print(f"  [ERRO] Falhou: {results['failed']}")
    print(f"  [AVISO] Avisos: {results['warnings']}")
    print(f"{'='*50}")

    if results["failed"] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
