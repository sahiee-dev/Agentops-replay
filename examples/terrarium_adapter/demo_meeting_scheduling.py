"""
Demo: AgentOps Replay + Terrarium MeetingScheduling Simulation

Simulates a Terrarium-style MeetingScheduling scenario using
AuditedBlackboardLogger. Produces a verifiable audit record.

Run: python3 examples/terrarium_adapter/demo_meeting_scheduling.py

No Terrarium installation required — simulates the blackboard events
that a real Terrarium run would produce.
"""
from __future__ import annotations
import json
import subprocess
import sys
import tempfile
from pathlib import Path

# Add AgentOps root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from examples.terrarium_adapter.terrarium_adapter import AuditedBlackboardLogger


def simulate_meeting_scheduling(log_dir: str) -> str:
    """
    Simulate a 3-agent MeetingScheduling DCOP scenario.

    Agents: alice, bob, charlie
    Task: coordinate a meeting slot
    Phases: planning → execution
    Iterations: 2
    """
    logger = AuditedBlackboardLogger(
        log_dir=log_dir,
        board_id="meeting_board_1",
    )

    # ── PLANNING PHASE ────────────────────────────────────────────────────────
    print("  Phase 1: Planning...")

    logger.log_blackboard_creation()
    logger.log_blackboard_join("alice")
    logger.log_blackboard_join("bob")
    logger.log_blackboard_join("charlie")

    # Iteration 1 — agents post availability
    board_state_1 = {
        "messages": [
            {"agent": "alice", "content_hash": "a" * 64,
             "proposal": "available: [9am, 2pm, 4pm]"},
        ],
        "iteration": 1,
        "phase": "planning",
    }
    logger.log_blackboard_state(
        "meeting_board_1", board_state_1, iteration=1, phase="planning"
    )

    # Iteration 2 — agents respond
    board_state_2 = {
        "messages": [
            {"agent": "alice", "content_hash": "a" * 64,
             "proposal": "available: [9am, 2pm, 4pm]"},
            {"agent": "bob", "content_hash": "b" * 64,
             "proposal": "available: [2pm, 3pm]"},
            {"agent": "charlie", "content_hash": "c" * 64,
             "proposal": "available: [9am, 2pm]"},
        ],
        "iteration": 2,
        "phase": "planning",
        "consensus": "2pm works for all agents",
    }
    logger.log_blackboard_state(
        "meeting_board_1", board_state_2, iteration=2, phase="planning"
    )

    # ── EXECUTION PHASE ───────────────────────────────────────────────────────
    print("  Phase 2: Execution...")

    board_state_3 = {
        "messages": board_state_2["messages"] + [
            {"agent": "system", "content_hash": "d" * 64,
             "action": "schedule_meeting(slot=2pm, attendees=[alice,bob,charlie])"},
        ],
        "iteration": 1,
        "phase": "execution",
        "decision": "MEETING_SCHEDULED",
        "slot": "2pm",
        "utility_score": 0.94,
    }
    logger.log_blackboard_state(
        "meeting_board_1", board_state_3, iteration=1, phase="execution"
    )

    logger.log_blackboard_exit("alice")
    logger.log_blackboard_exit("bob")
    logger.log_blackboard_exit("charlie")

    # ── FINALIZE ─────────────────────────────────────────────────────────────
    jsonl_path = logger.finalize()
    return jsonl_path


def main() -> None:
    print("=" * 60)
    print("AgentOps Replay × Terrarium — MeetingScheduling Demo")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmp:
        print(f"\nRunning MeetingScheduling simulation...")
        jsonl_path = simulate_meeting_scheduling(tmp)

        print(f"\nAudit record written: {jsonl_path}")

        # Count events
        events = [json.loads(l) for l in open(jsonl_path)]
        print(f"Events recorded: {len(events)}")
        print(f"Event types: {[e['event_type'] for e in events]}")

        # Verify
        print(f"\nVerifying audit record...")
        result = subprocess.run(
            ["python3", "verifier/agentops_verify.py",
             jsonl_path, "--format", "json"],
            capture_output=True, text=True,
            cwd=str(Path(__file__).parent.parent.parent)
        )

        if result.returncode != 0 and not result.stdout:
            print(f"Verifier error: {result.stderr}")
            sys.exit(1)

        data = json.loads(result.stdout)

        print(f"\nResult:         {data['result']}")
        print(f"Evidence class: {data['evidence_class']}")
        print(f"Checks passed:  {sum(1 for c in data.get('checks', {}).values() if c)}"
              f"/{len(data.get('checks', {}))}")

        if data["result"] == "PASS":
            print("\n✅ Terrarium scenario audit: PASS")
            print("   Every blackboard state is hash-chained and tamper-evident.")
            print("   This log cannot be modified without breaking the chain.")
        else:
            print("\n❌ Verification failed")
            sys.exit(1)

    print("\n" + "=" * 60)
    print("Demo complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
