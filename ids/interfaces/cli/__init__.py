"""CLI interface for IDS.

Provides a command-line REPL that implements the InterfaceAdapter protocol,
allowing IDS to run without Telegram or any external service dependency.
"""

from .adapter import CLIAdapter

__all__ = ["CLIAdapter"]
