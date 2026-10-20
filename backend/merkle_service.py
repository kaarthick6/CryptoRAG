"""Compatibility imports for the active local Merkle implementation."""

from app.services.merkle_service import (
    build_merkle_tree,
    create_merkle_proof,
    get_merkle_root,
    load_merkle_proof,
    save_merkle_tree,
    verify_merkle_proof,
)

__all__ = [
    "build_merkle_tree",
    "create_merkle_proof",
    "get_merkle_root",
    "load_merkle_proof",
    "save_merkle_tree",
    "verify_merkle_proof",
]
