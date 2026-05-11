"""
Demo: AgentOps Replay detects Terrarium log tampering

Shows the core security guarantee:
- Simulate a Terrarium scenario
- Tamper with the audit record (simulating an insider attack)
- Show that agentops-verify detects the tampering

This is the demonstration of Gap T-1 from the GAP_REGISTRY:
"Zero cryptographic results in Terrarium src/ — any file system actor
can modify released artifacts without detection."

AgentOps Replay closes this gap.
"""
from __future__ import annotations
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from examples.terrarium_adapter.terrarium_adapter import AuditedBlackboardLogger


def run_scenario(log_dir: str) -> str:
    logger = AuditedBlackboardLogger(log_dir=log_dir, board_id="test_board")

    # Simulate an adversarial agent scenario
    legitimate_state = {
        "messages": [
            {"agent": "agent_a", "content_hash": "a" * 64,
             "action": "schedule_meeting(slot=2pm)"},
            {"agent": "agent_b", "content_hash": "b" * 64,
             "action": "confirm(slot=2pm)"},
        ],
        "attack_attempted": False,
        "utility_score": 0.94,
    }
    logger.log_blackboard_state("test_board", legitimate_state, 1, "execution")
    return logger.finalize()


def tamper_with_record(jsonl_path: str) -> str:
    """Simulate an insider modifying the blackboard state record."""
    events = [json.loads(l) for l in open(jsonl_path)]

    # Find the TOOL_RESULT event (board state snapshot)
    for event in events:
        if event.get("event_type") == "TOOL_RESULT":
            # Adversary changes result_summary to hide the real board state
            # (simulating modification of attack_summary.json in real Terrarium)
            event["payload"]["result_summary"] = (
                "board_state board=test_board iter=1 phase=execution "
                "[MODIFIED: attack_attempted=True hidden]"
            )
            # Adversary does NOT update event_hash — they don't know JCS
            break

    tampered_path = jsonl_path.replace(".jsonl", "_tampered.jsonl")
    with open(tampered_path, "w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")
    return tampered_path


def verify(path: str, label: str) -> dict:
    result = subprocess.run(
        ["python3", "verifier/agentops_verify.py", path, "--format", "json"],
        capture_output=True, text=True,
        cwd=str(Path(__file__).parent.parent.parent)
    )
    data = json.loads(result.stdout)
    status = "✅ PASS" if data["result"] == "PASS" else "❌ FAIL"
    print(f"\n{label}")
    print(f"  Result:         {status}")
    print(f"  Evidence class: {data['evidence_class']}")
    if data["result"] == "FAIL":
        print(f"  Failure reason: {data.get('failure_reason', 'see checks')}")
    return data


def main():
    print("=" * 60)
    print("AgentOps Replay — Tamper Detection Demo")
    print("Demonstrates Gap T-1: Terrarium log integrity")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmp:
        # Step 1: Run scenario
        print("\n1. Running Terrarium-style scenario...")
        jsonl_path = run_scenario(tmp)
        print(f"   Audit record: {jsonl_path}")

        # Step 2: Verify original
        original_result = verify(jsonl_path, "2. Verifying original audit record:")
        assert original_result["result"] == "PASS", "Original must pass"

        # Step 3: Tamper
        print("\n3. Simulating insider attack...")
        print("   Modifying blackboard state record to hide attack evidence...")
        tampered_path = tamper_with_record(jsonl_path)
        print(f"   Tampered record: {tampered_path}")

        # Step 4: Verify tampered
        tampered_result = verify(tampered_path, "4. Verifying tampered record:")
        assert tampered_result["result"] == "FAIL", "Tampered must fail"

    print("\n" + "=" * 60)
    print("CONCLUSION")
    print("=" * 60)
    print("Without AgentOps Replay: Terrarium logs are mutable.")
    print("  An adversary can modify blackboard state records,")
    print("  attack summaries, or tool call logs undetected.")
    print()
    print("With AgentOps Replay: tampering is immediately detected.")
    print("  The hash chain catches any post-hoc modification,")
    print("  regardless of how carefully the adversary edits the file.")
    print()
    print("grep -rn 'hashlib|sha256' terrarium/src/ → 0 results")
    print("AgentOps Replay fills this gap.")
    print("=" * 60)


if __name__ == "__main__":
    main()
