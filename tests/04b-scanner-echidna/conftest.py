"""pytest configuration for 04b-scanner-echidna unit tests.

NOTE: sys.path manipulation is done inline in each test file, not here.
Each test file adds the echidna source path before imports and removes it
afterwards (sys.path.pop(0)), preventing namespace collision with the
other 27 services that also use ``src/`` as their package name.
"""
