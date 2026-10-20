"""Compatibility imports for legacy hash helper paths."""

from app.services.hashing_service import calculate_hash as calculate_sha256
from app.services.merkle_service import verify_merkle_proof


def calculate_merkle_root(leaf_hashes: list[str]) -> str:
    """Calculate a domain-separated Merkle root from chunk hashes."""
    from app.services.merkle_service import build_merkle_tree, get_merkle_root

    return get_merkle_root(build_merkle_tree(leaf_hashes))
