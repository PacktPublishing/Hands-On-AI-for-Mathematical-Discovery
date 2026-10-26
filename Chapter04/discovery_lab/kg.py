"""Knowledge graph of definitions, claims, evidence, and sources."""

import networkx as nx
from .ledger import Evidence


class MathKG:
    NODE_KINDS = {
        "definition",
        "claim",
        "example",
        "counterexample",
        "proof",
        "source",
    }
    RELATIONS = {
        "supports",
        "refutes",
        "refines",
        "proves",
        "uses",
        "cites",
    }

    def __init__(self):
        self.g = nx.MultiDiGraph()

    def add(self, node_id, kind, statement, **meta):
        assert kind in self.NODE_KINDS, kind
        self.g.add_node(
            node_id, kind=kind, statement=statement, **meta
        )
        return node_id

    def relate(self, src, rel, dst, **meta):
        assert rel in self.RELATIONS, rel
        self.g.add_edge(src, dst, key=rel, **meta)

    def set_evidence(self, claim_id, level):
        self.g.nodes[claim_id]["evidence"] = Evidence(level)

    def claims(self, min_level=Evidence.REFUTED):
        return [
            n
            for n, d in self.g.nodes(data=True)
            if d["kind"] == "claim"
            and d.get("evidence", Evidence.PROPOSED) >= min_level
        ]

    def known(self, statement, exclude=None):
        """Novelty check against everything the graph already contains."""
        return any(
            d["statement"] == statement
            for n, d in self.g.nodes(data=True)
            if n != exclude
        )

    def neighborhood(self, node_id):
        return [
            (u, k, v)
            for u, v, k in self.g.in_edges(node_id, keys=True)
        ] + [
            (u, k, v)
            for u, v, k in self.g.out_edges(node_id, keys=True)
        ]
