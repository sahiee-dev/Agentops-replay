# backend/app/core/refactor_engine.py

import ast

from sentence_transformers import SentenceTransformer, util

model = SentenceTransformer("all-MiniLM-L6-v2")


class HybridRefactor:
    def __init__(self):
        self.model = model

    def ast_optimize(self, code):
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == "foo":
                    node.name = "optimized_foo"
            return ast.unparse(tree)
        except Exception:
            return code

    def semantic_refine(self, orig, ref):
        orig_vec, ref_vec = self.model.encode([orig, ref])
        score = util.cos_sim(orig_vec, ref_vec).item()
        if score < 0.8:
            # apply lightweight semantic edit
            ref = ref.replace("temp", "result")
        return ref, score

    def hybrid_refactor(self, code):
        ast_ref = self.ast_optimize(code)
        refined, sem_score = self.semantic_refine(code, ast_ref)
        return refined, sem_score
