# backend/app/core/replay_learning.py
from app.core.refactor_engine import HybridRefactor
from app.models.session import Session
from app.database import get_db

def learn_from_replays(db=None):
    db = db or next(get_db())
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
