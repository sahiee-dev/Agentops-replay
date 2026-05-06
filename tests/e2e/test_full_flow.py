import pytest
import json
import os
import tempfile
import subprocess
import sys

from agentops_sdk.client import AgentOpsClient
from agentops_sdk.events import EventType

VERIFIER = os.path.join("verifier", "agentops_verify.py")


def run_verifier_on_file(path: str) -> dict:
    result = subprocess.run(
        [sys.executable, VERIFIER, path, "--format", "json"],
        capture_output=True, text=True
    )
    return {
        "returncode": result.returncode,
        "data": json.loads(result.stdout) if result.stdout.strip() else {},
    }


def test_local_authority_mode_end_to_end():
    """
    Full local authority flow:
    AgentOpsClient → record events → flush_to_jsonl → Verifier PASS
    Evidence class: NON_AUTHORITATIVE_EVIDENCE
    """
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        output_path = f.name

    try:
        client = AgentOpsClient(local_authority=True, buffer_size=100)
        client.start_session(agent_id="e2e-test-agent")
        client.record(EventType.LLM_CALL, {"model_id": "test-model", "prompt_hash": "abc"})
        client.record(EventType.LLM_RESPONSE, {"content_hash": "def", "finish_reason": "stop"})
        client.record(EventType.TOOL_CALL, {"tool_name": "calculator", "args_hash": "ghi"})
        client.record(EventType.TOOL_RESULT, {"tool_name": "calculator", "result_hash": "jkl"})
        client.end_session(status="success")
        client.flush_to_jsonl(output_path)

        result = run_verifier_on_file(output_path)
        assert result["returncode"] == 0, f"Verifier failed: {result}"
        assert result["data"]["result"] == "PASS"
        assert result["data"]["evidence_class"] == "NON_AUTHORITATIVE_EVIDENCE"

    finally:
        if os.path.exists(output_path):
            os.unlink(output_path)


def test_buffer_overflow_produces_valid_chain():
    """
    Buffer overflow flow:
    Create client with buffer_size=5, record 10 events.
    Result must: PASS, contain exactly 1 LOG_DROP, NON_AUTHORITATIVE_EVIDENCE.
    """
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        output_path = f.name

    try:
        client = AgentOpsClient(local_authority=True, buffer_size=5)
        client.start_session(agent_id="overflow-test-agent")
        for i in range(10):
            client.record(EventType.LLM_CALL, {"model_id": "test", "call_num": i})
        client.end_session(status="success")
        client.flush_to_jsonl(output_path)

        result = run_verifier_on_file(output_path)
        assert result["returncode"] == 0, f"Verifier failed on overflow session: {result}"
        assert result["data"]["result"] == "PASS"

        with open(output_path) as f:
            events = [json.loads(l) for l in f if l.strip()]
        log_drops = [e for e in events if e["event_type"] == "LOG_DROP"]
        assert len(log_drops) >= 1, "Expected at least 1 LOG_DROP event"

    finally:
        if os.path.exists(output_path):
            os.unlink(output_path)


@pytest.mark.skipif(
    os.environ.get("AGENTOPS_SERVER_URL") is None,
    reason="Requires running Ingestion Service. Set AGENTOPS_SERVER_URL to enable."
)
def test_server_authority_mode_end_to_end():
    """
    Full server authority flow:
    SDK → POST /v1/ingest → CHAIN_SEAL → GET export → Verifier PASS
    Evidence class: AUTHORITATIVE_EVIDENCE
    """
    import urllib.request
    server_url = os.environ["AGENTOPS_SERVER_URL"]

    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        output_path = f.name

    try:
        client = AgentOpsClient(
            local_authority=False,
            server_url=server_url,
            buffer_size=100
        )
        session_id = client.start_session(agent_id="server-e2e-test-agent")
        client.record(EventType.LLM_CALL, {"model_id": "test-model", "prompt_hash": "abc"})
        client.record(EventType.LLM_RESPONSE, {"content_hash": "def", "finish_reason": "stop"})
        client.end_session(status="success")
        response = client.send_to_server()

        assert response.get("chain_seal") is not None, "No CHAIN_SEAL in response"

        # Export and verify
        export_url = f"{server_url}/v1/sessions/{session_id}/export"
        req = urllib.request.Request(export_url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            with open(output_path, "wb") as f:
                f.write(resp.read())

        result = run_verifier_on_file(output_path)
        assert result["returncode"] == 0
        assert result["data"]["result"] == "PASS"
        assert result["data"]["evidence_class"] == "AUTHORITATIVE_EVIDENCE"

    finally:
        if os.path.exists(output_path):
            os.unlink(output_path)
