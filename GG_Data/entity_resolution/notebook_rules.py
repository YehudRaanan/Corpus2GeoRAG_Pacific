"""The notebook's fixed, untrained HITS and suggestion rules."""

import networkx as nx
import pandas as pd


def hits_steps(g: nx.DiGraph, steps: int, *, keep_history: bool = True) -> pd.DataFrame:
    hubs = dict.fromkeys(g, 1 / max(len(g), 1))
    history = []
    for step in range(1, steps + 1):
        authority = {q: sum(hubs[p] for p in g.predecessors(q)) for q in g}
        scale = sum(authority.values()) or 1.0
        authority = {q: score / scale for q, score in authority.items()}
        hubs = {q: sum(authority[t] for t in g.successors(q)) for q in g}
        scale = sum(hubs.values()) or 1.0
        hubs = {q: score / scale for q, score in hubs.items()}
        if keep_history or step == steps:
            history.extend(
                {"iteration": step, "qid": q, "authority": authority[q], "hub": hubs[q]}
                for q in g
            )
    return pd.DataFrame(history, columns=["iteration", "qid", "authority", "hub"])


def decide(options: pd.DataFrame, min_name: float, min_gap: float) -> dict:
    if options.empty:
        return {
            "suggested_qid": None,
            "decision": "UNRESOLVED",
            "reason": "no candidate in page pool",
            "authority_gap": None,
        }
    options = options.sort_values(
        ["authority", "name_similarity", "qid"], ascending=[False, False, True]
    )
    best = options.iloc[0]
    gap = (
        None
        if len(options) == 1
        else (
            (best.authority - options.iloc[1].authority) / best.authority
            if best.authority > 0
            else 0.0
        )
    )
    accepted = best.name_similarity >= min_name and (
        len(options) == 1 or (gap > 0 and gap >= min_gap)
    )
    reason = (
        "single candidate; name rule passed"
        if len(options) == 1
        else "graph winner; name and gap rules passed"
    )
    return {
        "suggested_qid": best.qid if accepted else None,
        "decision": "SUGGESTED" if accepted else "UNRESOLVED",
        "reason": reason if accepted else "name score or graph separation too weak",
        "authority_gap": gap,
    }
