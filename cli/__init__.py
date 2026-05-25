"""Vyper CLI — Smart Contract Bug Hunter.

Usage:
    vyper audit <address>          Full audit pipeline
    vyper scan <file>              Quick scan (slither + mythril + echidna)
    vyper exploit <finding-id>     Generate PoC exploit
    vyper status <audit-id>        Check audit status
    vyper list                     List all audits
    vyper stats                    Pipeline statistics
    vyper queue                    View priority queue
    vyper health                   Check all service health
    vyper agent status             Show Antonio agent overview
    vyper agent session <id>       Show agent session details
    vyper agent learn              Show agent learning insights
    vyper doctor                   Run system diagnostic
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
