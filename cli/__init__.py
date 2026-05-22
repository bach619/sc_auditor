"""Vyper backend library — Python modules for Vyper microservices.

The Vyper CLI has been migrated to Go (cmd/vyper/).
This Python library remains for backend service imports.

Go CLI usage:
    vyper audit <address>          Full audit pipeline
    vyper scan <file>              Quick scan (slither + mythril + echidna)
    vyper exploit <finding-id>     Generate PoC exploit
    vyper status <audit-id>        Check audit status
    vyper list                     List all audits
    vyper stats                    Pipeline statistics
    vyper queue                    View priority queue
    vyper health                   Check all service health
    vyper up                       Start all Docker services
    vyper down                     Stop all Docker services
    vyper logs [service]           View service logs
    vyper ps                       Show running services
    vyper restart [service]        Restart services
    vyper config                   Show/edit configuration
    vyper version                  Show version
"""

__version__ = "0.2.0"
__author__ = "Vyper Team"
