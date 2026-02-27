def levenshtein_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    if len(a) < len(b):
        a, b = b, a

    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            insert_cost = current[j - 1] + 1
            delete_cost = previous[j] + 1
            replace_cost = previous[j - 1] + (0 if ca == cb else 1)
            current.append(min(insert_cost, delete_cost, replace_cost))
        previous = current

    return previous[-1]


def normalized_similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    denom = max(len(a), len(b))
    if denom == 0:
        return 1.0
    d = levenshtein_distance(a, b)
    return 1.0 - (d / denom)
