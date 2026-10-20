"""Tests for Merkle tree structure and inclusion proofs."""

import pytest

from app.services.hashing_service import calculate_hash
from app.services.merkle_service import (
    build_merkle_tree,
    create_merkle_proof,
    get_merkle_root,
    verify_merkle_proof,
)


@pytest.mark.parametrize("texts", [["one"], ["one", "two"], ["one", "two", "three"]])
def test_proof_verifies_for_single_even_and_odd_leaf_counts(texts):
    leaves = [calculate_hash(text) for text in texts]
    tree = build_merkle_tree(leaves)
    root = get_merkle_root(tree)

    for index, leaf in enumerate(leaves):
        proof = create_merkle_proof(tree, index)
        assert verify_merkle_proof(leaf, proof, root)


def test_modified_leaf_does_not_verify():
    tree = build_merkle_tree([calculate_hash("one"), calculate_hash("two")])
    proof = create_merkle_proof(tree, 0)
    assert not verify_merkle_proof(
        calculate_hash("changed"), proof, get_merkle_root(tree)
    )


def test_modified_sibling_and_wrong_root_do_not_verify():
    leaf = calculate_hash("one")
    tree = build_merkle_tree([leaf, calculate_hash("two")])
    proof = create_merkle_proof(tree, 0)
    modified_proof = [{"side": "right", "hash": "00" * 32}]

    assert not verify_merkle_proof(leaf, modified_proof, get_merkle_root(tree))
    assert not verify_merkle_proof(leaf, proof, "ff" * 32)


def test_reordered_siblings_do_not_verify():
    leaves = [calculate_hash(text) for text in ["one", "two", "three"]]
    tree = build_merkle_tree(leaves)
    proof = create_merkle_proof(tree, 2)

    assert not verify_merkle_proof(
        leaves[2], list(reversed(proof)), get_merkle_root(tree)
    )


@pytest.mark.parametrize("proof", [None, [{}], [{"side": "up", "hash": "00" * 32}]])
def test_malformed_proof_is_rejected(proof):
    assert not verify_merkle_proof(calculate_hash("one"), proof, "00" * 32)


def test_empty_tree_and_invalid_index_are_rejected():
    with pytest.raises(ValueError):
        build_merkle_tree([])
    tree = build_merkle_tree([calculate_hash("one")])
    with pytest.raises(ValueError):
        create_merkle_proof(tree, 1)
