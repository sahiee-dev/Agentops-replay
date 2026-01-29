"""
Ingestion service package.

This package implements server-side authority for event chains.
"""

from .hasher import recompute_chain, ChainResult, RejectionReason
from .sealer import seal_chain, SealResult

__all__ = [
    'recompute_chain',
    'ChainResult',
    'RejectionReason',
    'seal_chain',
    'SealResult',
]
