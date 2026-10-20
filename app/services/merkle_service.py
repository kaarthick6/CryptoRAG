"""Domain-separated local Merkle tree construction and proof verification."""

import hashlib


def hash_leaf(leaf_hash: str) -> bytes:
    """Hash a chunk digest as a leaf with a type prefix."""
    return hashlib.sha256(b"\x00" + bytes.fromhex(leaf_hash)).digest()


def hash_parent(left_hash: bytes, right_hash: bytes) -> bytes:
    """Hash two binary child nodes with an internal-node prefix."""
    return hashlib.sha256(b"\x01" + left_hash + right_hash).digest()


def build_merkle_tree(chunk_hashes: list[str]) -> list[list[bytes]]:
    """Build levels from leaf to root, duplicating an unmatched final node."""
    if not chunk_hashes:
        raise ValueError("A Merkle tree requires at least one chunk hash")

    leaves = [hash_leaf(chunk_hash) for chunk_hash in chunk_hashes]
    levels = [leaves]
    current_level = leaves

    while len(current_level) > 1:
        next_level = []
        for index in range(0, len(current_level), 2):
            left_hash = current_level[index]
            if index + 1 < len(current_level):
                right_hash = current_level[index + 1]
            else:
                right_hash = left_hash
            next_level.append(hash_parent(left_hash, right_hash))
        levels.append(next_level)
        current_level = next_level
    return levels


def get_merkle_root(tree: list[list[bytes]]) -> str:
    """Return the root as lowercase hexadecimal text."""
    if not tree or not tree[-1]:
        raise ValueError("Merkle tree has no root")
    return tree[-1][0].hex()


def create_merkle_proof(tree: list[list[bytes]], leaf_index: int) -> list[dict]:
    """Return ordered sibling hashes and left/right positions for one leaf."""
    if not tree or leaf_index < 0 or leaf_index >= len(tree[0]):
        raise ValueError("Merkle proof leaf index is out of range")

    proof = []
    current_index = leaf_index
    for level in tree[:-1]:
        sibling_index = current_index - 1 if current_index % 2 else current_index + 1
        if sibling_index >= len(level):
            sibling_index = current_index
        side = "left" if sibling_index < current_index else "right"
        proof.append({"hash": level[sibling_index].hex(), "side": side})
        current_index //= 2
    return proof


def verify_merkle_proof(leaf_hash: str, proof: list[dict], expected_root: str) -> bool:
    """Rebuild the root in proof order and reject malformed nodes safely."""
    try:
        calculated_hash = hash_leaf(leaf_hash)
        for proof_item in proof:
            sibling_hash = bytes.fromhex(proof_item["hash"])
            if len(sibling_hash) != 32:
                return False
            if proof_item["side"] == "left":
                calculated_hash = hash_parent(sibling_hash, calculated_hash)
            elif proof_item["side"] == "right":
                calculated_hash = hash_parent(calculated_hash, sibling_hash)
            else:
                return False
        return calculated_hash.hex() == expected_root
    except (KeyError, TypeError, ValueError):
        return False


def save_merkle_tree(
    repository, document_id: str, version: str, tree: list[list[bytes]]
) -> None:
    """Persist root and each chunk proof using the metadata repository."""
    repository.save_merkle_data(document_id, version, get_merkle_root(tree))


def load_merkle_proof(
    repository, document_id: str, version: str, chunk_id: str
) -> list[dict] | None:
    """Load a previously saved proof from the metadata repository."""
    return repository.load_merkle_proof(document_id, version, chunk_id)
