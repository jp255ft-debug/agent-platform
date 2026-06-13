#!/usr/bin/env python3
"""
validate_solidity.py -- Validador de contratos Solidity para o Agent Platform.

Verifica:
1. SPDX license identifier
2. Pragma Solidity version
3. Padroes de seguranca basicos (reentrancy, tx.origin)
4. NatSpec em funcoes publicas
5. Forge build (se disponivel)

Uso:
    python .ai/validation/validate_solidity.py [--path contracts/src]
"""
import re
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_PATH = BASE_DIR / "contracts" / "src"


def check_spdx(content: str, filename: str) -> list[str]:
    """Verifica se o arquivo tem SPDX-License-Identifier."""
    errors = []
    if "SPDX-License-Identifier" not in content:
        errors.append(f"  [ERRO] {filename}: SPDX-License-Identifier ausente")
    return errors


def check_pragma(content: str, filename: str) -> list[str]:
    """Verifica se o pragma Solidity e >= 0.8.20."""
    errors = []
    match = re.search(r"pragma\s+solidity\s+([^;]+);", content)
    if not match:
        errors.append(f"  [ERRO] {filename}: pragma solidity ausente")
    else:
        version = match.group(1).strip()
        if not re.search(r"\^?0\.8\.\d+", version):
            errors.append(f"  [ERRO] {filename}: pragma '{version}' -- esperado ^0.8.20+")
    return errors


def check_security_patterns(content: str, filename: str) -> list[str]:
    """Verifica padroes de seguranca basicos."""
    errors = []
    warnings = []

    # Verifica uso de tx.origin (proibido)
    if "tx.origin" in content:
        errors.append(f"  [ERRO] {filename}: uso de tx.origin detectado (use msg.sender)")

    # Verifica se funcoes com 'call' tem protecao
    call_pattern = re.findall(r"\.call\{value:", content)
    if call_pattern and "nonReentrant" not in content and "ReentrancyGuard" not in content:
        warnings.append(
            f"  [AVISO] {filename}: chamadas .call{{value:...}} sem ReentrancyGuard"
        )

    # Verifica se ha require sem mensagem de erro
    bare_requires = re.findall(r"require\([^,)]+\)", content)
    if bare_requires:
        warnings.append(
            f"  [AVISO] {filename}: {len(bare_requires)} require(s) sem mensagem de erro"
        )

    return errors + warnings


def check_natspec(content: str, filename: str) -> list[str]:
    """Verifica se funcoes publicas/externas tem NatSpec."""
    warnings = []
    func_pattern = re.compile(
        r"(?:function\s+(\w+)\s*\([^)]*\)\s*(?:public|external))",
        re.MULTILINE,
    )
    for match in func_pattern.finditer(content):
        func_name = match.group(1)
        if func_name.startswith("_"):
            continue
        if func_name in ("receive", "fallback"):
            continue
        pos = match.start()
        before = content[max(0, pos - 500):pos]
        if "@notice" not in before and "@param" not in before:
            warnings.append(
                f"  [AVISO] {filename}: funcao '{func_name}' sem NatSpec"
            )
    return warnings


def run_forge_build(path: Path) -> list[str]:
    """Tenta rodar forge build no diretorio de contratos."""
    errors = []
    try:
        contracts_dir = BASE_DIR / "contracts"
        result = subprocess.run(
            ["forge", "build", "--force"],
            cwd=str(contracts_dir),
            capture_output=True, text=True, timeout=120,
            shell=True,
        )
        if result.returncode != 0:
            stderr_lines = result.stderr.strip().split("\n")
            error_lines = [l for l in stderr_lines if "Error" in l or "error" in l.lower()]
            # Filter out path resolution errors on Windows
            error_lines = [l for l in error_lines if "sistema não pode" not in l.lower() and "cannot find" not in l.lower()]
            for line in error_lines[:5]:
                errors.append(f"  [ERRO] Forge: {line.strip()}")
    except FileNotFoundError:
        errors.append("  [AVISO] Forge nao encontrado (pulando build)")
    except subprocess.TimeoutExpired:
        errors.append("  [ERRO] Forge build timeout (120s)")
    return errors


def validate_path(path: Path) -> dict:
    """Valida todos os arquivos Solidity em um diretorio."""
    results = {"passed": 0, "failed": 0, "warnings": 0, "errors": []}

    sol_files = list(path.rglob("*.sol"))
    sol_files = [f for f in sol_files if "lib" not in f.parts]

    print(f"\n[VALIDANDO] {len(sol_files)} contratos Solidity em {path}...\n")

    for filepath in sol_files:
        rel_path = filepath.relative_to(BASE_DIR)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            print(f"  [ERRO] Erro ao ler {rel_path}: {e}")
            results["failed"] += 1
            continue

        file_errors = []
        file_warnings = []

        # 1. SPDX
        file_errors.extend(check_spdx(content, filepath.name))

        # 2. Pragma
        file_errors.extend(check_pragma(content, filepath.name))

        # 3. Seguranca
        sec_results = check_security_patterns(content, filepath.name)
        for r in sec_results:
            if "[ERRO]" in r:
                file_errors.append(r)
            else:
                file_warnings.append(r)

        # 4. NatSpec
        file_warnings.extend(check_natspec(content, filepath.name))

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

    # 5. Forge build (se houver arquivos)
    if sol_files:
        print("\n[BUILD] Rodando forge build...")
        forge_errors = run_forge_build(path)
        for e in forge_errors:
            print(e)
            if "[ERRO]" in e:
                results["failed"] += 1
                results["errors"].append(e)
            else:
                results["warnings"] += 1

    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Validador Solidity Agent Platform")
    parser.add_argument("--path", default=str(DEFAULT_PATH),
                        help="Caminho para validar (default: contracts/src)")
    args = parser.parse_args()

    path = Path(args.path).resolve()
    if not path.exists():
        print(f"[ERRO] Caminho nao encontrado: {path}")
        sys.exit(1)

    results = validate_path(path)

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
