"""
src/analysis/correlation.py
===========================
Automatic double-count removal (Phase 3).

The trend category contains several **highly correlated** sub-signals
(``Price > SMA50``, ``Price > SMA200``, ``SMA50 > SMA200``, ``EMA20 > EMA50``,
...). In a sustained trend they all fire together, so scoring them
independently counts a single phenomenon many times and inflates the score.

This module detects correlated signals *automatically* from their historical
boolean series and assigns weights so that a cluster of correlated signals
contributes (roughly) the weight of a **single** independent signal.

Algorithm
---------
1. Compute the pairwise correlation matrix of the signal series.
2. Union-find: any two signals with ``|corr| >= threshold`` join the same
   cluster (transitive — A~B and B~C ⇒ {A,B,C}).
3. Each of the ``K`` resulting clusters receives total weight ``1 / K``, split
   equally among its members.

So six perfectly collinear MA signals collapse into one cluster carrying the
weight of one signal, while genuinely independent signals keep their full
weight. Weights always sum to 1.
"""

from __future__ import annotations

from typing import Dict, List

import pandas as pd


class _UnionFind:
    def __init__(self, items: List[str]):
        self.parent = {x: x for x in items}

    def find(self, x: str) -> str:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def cluster_signals(frame: pd.DataFrame, threshold: float) -> List[List[str]]:
    """
    Group columns of *frame* into clusters of mutually correlated signals.

    A constant column (no variance) cannot correlate with anything and is
    returned as its own singleton cluster.
    """
    cols = list(frame.columns)
    uf = _UnionFind(cols)

    # Pearson correlation; constant columns -> NaN, treated as uncorrelated.
    corr = frame.astype(float).corr()

    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            c = corr.loc[a, b]
            if pd.notna(c) and abs(c) >= threshold:
                uf.union(a, b)

    clusters: Dict[str, List[str]] = {}
    for col in cols:
        clusters.setdefault(uf.find(col), []).append(col)
    return list(clusters.values())


def cluster_weights(frame: pd.DataFrame, threshold: float = 0.85) -> Dict[str, float]:
    """
    Return ``{signal_name: weight}`` with correlated signals de-duplicated.

    Each cluster gets ``1 / num_clusters`` total weight, divided equally among
    its members. Weights sum to 1. An empty frame returns ``{}``.
    """
    if frame.shape[1] == 0:
        return {}

    clean = frame.dropna(how="all", axis=1)
    if clean.shape[1] == 0:
        # All-NaN: fall back to equal weights over the original columns.
        n = frame.shape[1]
        return {c: 1.0 / n for c in frame.columns}

    clusters = cluster_signals(clean, threshold)
    k = len(clusters)
    weights: Dict[str, float] = {}
    for cluster in clusters:
        per_member = (1.0 / k) / len(cluster)
        for name in cluster:
            weights[name] = per_member

    # Any column dropped as all-NaN gets zero weight (no data to contribute).
    for c in frame.columns:
        weights.setdefault(c, 0.0)
    return weights


def effective_independent_count(frame: pd.DataFrame, threshold: float = 0.85) -> int:
    """Number of de-correlated 'concepts' (clusters) among the signals."""
    clean = frame.dropna(how="all", axis=1)
    if clean.shape[1] == 0:
        return 0
    return len(cluster_signals(clean, threshold))
