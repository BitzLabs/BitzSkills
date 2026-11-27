"""Identify development cases affected by duplicate or unassessed comparisons."""


def novelty_blockers(case_id, judgments, peer_ids=None):
    affected_indices = judgments["D"] | judgments["U"]
    if not affected_indices:
        return set()
    blocked = {case_id}
    if peer_ids is not None:
        blocked.update(peer_ids[index - 1] for index in affected_indices)
    return blocked
