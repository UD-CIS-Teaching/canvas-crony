import math


def f(x):
    return f"{x:.2f}".rstrip("0").rstrip(".")


def iqr(scores):
    if not scores:
        return ["", "", "", "", ""]
    scores = sorted(scores)
    n = len(scores)
    q1 = scores[min(n - 1, math.ceil(n * 0.25))]
    median = scores[min(n - 1, math.ceil(n * 0.5))]
    q3 = scores[min(n - 1, math.ceil(n * 0.75))]
    # return [str(scores[0]), str(q1), str(median), str(q3), str(scores[-1])]
    return [
        f(scores[0]),
        f(q1),
        f(median),
        f(q3),
        f(scores[-1]),
    ]


def get_normal_stats(scores):
    if not scores:
        return ["", "", ""]
    mean = sum(scores) / len(scores)
    variance = sum((x - mean) ** 2 for x in scores) / len(scores)
    std_dev = math.sqrt(variance)
    return [f(mean), f(variance), f(std_dev)]
