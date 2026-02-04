# metrics.py
from radon.complexity import cc_visit
from radon.metrics import mi_visit
from sentence_transformers import SentenceTransformer, util

model = SentenceTransformer("all-MiniLM-L6-v2")


def structural_score(code):
    try:
        results = cc_visit(code)
        avg_complexity = sum([r.complexity for r in results]) / len(results)
        return max(0, 1 - (avg_complexity / 10))  # normalize
    except:
        return 0.5


def semantic_score(orig, ref):
    e1, e2 = model.encode(orig), model.encode(ref)
    return float(util.cos_sim(e1, e2))


def maintainability_score(code):
    try:
        mi = mi_visit(code, True)
        return min(1.0, mi / 100)
    except:
        return 0.5


def combined_score(orig, ref):
    s = structural_score(ref)
    m = maintainability_score(ref)
    sem = semantic_score(orig, ref)
    return {"struct": s, "maint": m, "semantic": sem, "overall": (s + m + sem) / 3}


if __name__ == "__main__":
    orig = "def add(a,b): return a+b"
    ref = "def sum_nums(a,b): return a+b"
    print(combined_score(orig, ref))
