"""
Ingestion service package.

This package implements server-side authority for event chains.
"""

from .hasher import ChainResult, RejectionReason, recompute_chain
from .sealer import SealResult, seal_chain

__all__ = [
    'ChainResult',
    'RejectionReason',
    'SealResult',
    'recompute_chain',
    'seal_chain',
]
