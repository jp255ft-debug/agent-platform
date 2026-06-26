"""Root conftest - patches web3 pytest plugin before it loads."""
import sys

# The web3 pytest11 entrypoint was removed from the package metadata
# (web3-6.11.1.dist-info/entry_points.txt) to prevent ImportError:
#   cannot import name 'ContractName' from 'eth_typing'
#
# This conftest provides a fallback mock in case the entrypoint is
# still present in some environments.
from types import ModuleType

if "web3.tools.pytest_ethereum" not in sys.modules:
    mock_pytest_ethereum = ModuleType("web3.tools.pytest_ethereum")
    mock_pytest_ethereum.__path__ = []
    mock_pytest_ethereum.plugins = ModuleType("web3.tools.pytest_ethereum.plugins")
    sys.modules["web3.tools.pytest_ethereum"] = mock_pytest_ethereum
    sys.modules["web3.tools.pytest_ethereum.plugins"] = mock_pytest_ethereum.plugins
