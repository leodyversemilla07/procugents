"""Pytest configuration for ProCuGents test suite.

Sets ``pytest-asyncio`` to ``auto`` mode across the suite.
"""
# Auto mode is what we want: any ``async def test_*`` runs in an event loop
# without the per-test decorator overhead.
