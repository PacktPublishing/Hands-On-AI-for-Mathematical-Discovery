"""Exhaustive cycle census by parity words, up to a length."""

from .maps import (
    cycle_from_word,
    is_cycle,
    is_primitive,
    rotate_to_min,
    step,
)


def lyndon_words(max_len):
    """All binary Lyndon words of length 1..max_len (Duval).

    Every cycle has exactly one rotation of its parity word that is
    a Lyndon word, so each cycle is found exactly once.
    """
    w = [-1]
    while w:
        w[-1] += 1
        yield "".join(map(str, w))
        m = len(w)
        while len(w) < max_len:
            w.append(w[len(w) - m])
        while w and w[-1] == 1:
            w.pop()


def census(q, c, max_len, positive=True):
    """All cycles of T_{q,c} with a period of at most max_len.

    Returns a list of dicts sorted by smallest member. Complete by
    construction: every such cycle has a Lyndon parity word of
    length <= max_len, and every such word is tested.
    """
    found = []
    for word in lyndon_words(max_len):
        x0 = cycle_from_word(q, c, word)
        if x0.denominator != 1 or (positive and x0 <= 0):
            continue
        members, x = [], int(x0)
        for _ in word:
            members.append(x)
            x = step(q, c, x)
        assert x == members[0] and is_cycle(q, c, members)
        i = members.index(min(members))
        found.append(
            {
                "smallest": min(members),
                "period": len(word),
                "odd_steps": word.count("1"),
                "word": word[i:] + word[:i],
                "members": members[i:] + members[:i],
                "primitive": is_primitive(c, members),
            }
        )
    return sorted(found, key=lambda f: f["smallest"])


def survey(q, c, x_max, budget=200_000, limit=10**100):
    """Cycles reached from the starting values 1..x_max.

    Not complete: a cycle that no orbit from 1..x_max reaches is
    missed. Returns (cycles by smallest member, number of starts
    whose orbits grew beyond limit, last start examined).
    """
    fate, cycles, escaped, steps = {}, {}, 0, 0
    for start in range(1, x_max + 1):
        index, x = {}, start
        while (
            x not in fate and x not in index and abs(x) <= limit
        ):
            if steps == budget:
                return cycles, escaped, start - 1
            index[x] = len(index)
            x = step(q, c, x)
            steps += 1
        if x in fate:
            key = fate[x]
        elif x in index:  # the orbit closed a new cycle
            first = index[x]
            key = min(y for y, i in index.items() if i >= first)
            cycles[key] = rotate_to_min(
                [y for y, i in index.items() if i >= first]
            )
        else:  # the orbit grew beyond limit
            key = None
        escaped += key is None
        for y in index:
            fate[y] = key
    return cycles, escaped, x_max
