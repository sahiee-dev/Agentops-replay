# backend/app/core/replay_learning.py
from app.core.refactor_engine import HybridRefactor
from app.database import get_db
from app.models.session import Session


def learn_from_replays(db=None):
    gen = get_db()
    db = db or next(gen)
    try:
        ref = HybridRefactor()
        sessions = db.query(Session).all()
        for s in sessions:
            if "error" in s.log_data.lower():
                improved, score = ref.hybrid_refactor(s.code_snapshot)
                # Save improvement
                s.refactored_code = improved
                s.refactor_score = score
                db.add(s)
        db.commit()
    finally:
        if db:
            gen.close()
