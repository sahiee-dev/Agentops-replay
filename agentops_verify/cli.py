#!/usr/bin/env python3
"""
agentops_verify/cli.py - Command-Line Interface

Usage:
    python -m agentops_verify.cli verify session_golden.json
    python -m agentops_verify.cli verify session_golden.json --output report.json

Exit Codes:
    0 = PASS
    1 = DEGRADED
    2 = FAIL
"""
import argparse
import json
import sys
from pathlib import Path

from .verifier import verify_file, TRUSTED_AUTHORITIES
from .errors import VerificationStatus


def main():
    """
    Parse command-line arguments and dispatch the agentops-verify command-line interface.
    
    Defines a required "verify" subcommand that validates a sealed session file and delegates execution to run_verify(args).
    The "verify" subcommand accepts:
    - session_file: path to session_golden.json
    - --output / -o: optional path to write a JSON verification report
    - --authorities: optional list of trusted authority identifiers (defaults to TRUSTED_AUTHORITIES)
    - --quiet / -q: suppress verbose output and only emit the exit code
    """
    parser = argparse.ArgumentParser(
        prog="agentops-verify",
        description="Production Verifier for AgentOps Evidence"
    )
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # verify command
    verify_parser = subparsers.add_parser("verify", help="Verify a sealed session")
    verify_parser.add_argument("session_file", help="Path to session_golden.json")
    verify_parser.add_argument(
        "--output", "-o",
        help="Path to write verification_report.json"
    )
    verify_parser.add_argument(
        "--authorities",
        nargs="+",
        default=list(TRUSTED_AUTHORITIES),
        help="Trusted authority identifiers"
    )
    verify_parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Only output exit code"
    )
    
    args = parser.parse_args()
    
    if args.command == "verify":
        run_verify(args)


def run_verify(args):
    """
    Run the verify subcommand for a session file and produce a verification report.
    
    Parameters:
        args (argparse.Namespace): Parsed CLI arguments with the following expected attributes:
            session_file (str): Path to the sealed session JSON file to verify (session_golden.json).
            output (str | None): Optional path to write the verification report as JSON.
            authorities (Iterable[str]): Trusted authorities to use for verification.
            quiet (bool): If true, suppress verbose console output.
    
    Behavior:
        - Verifies the provided session file using the configured trusted authorities.
        - If `output` is provided, writes the report as JSON to that path.
        - Unless `quiet` is set, prints a concise verification summary and any findings to stdout.
        - Exits the process with the verification report's `exit_code`.
        - Exits with code 2 if the session file is missing or verification fails.
    """
    session_path = Path(args.session_file)
    
    if not session_path.exists():
        print(f"Error: File not found: {session_path}", file=sys.stderr)
        sys.exit(2)
    
    try:
        report = verify_file(
            str(session_path),
            trusted_authorities=set(args.authorities)
        )
    except Exception as e:
        print(f"Error: Verification failed: {e}", file=sys.stderr)
        sys.exit(2)
    
    # Output report
    report_dict = report.to_dict()
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(report_dict, f, indent=2)
        if not args.quiet:
            print(f"Report written to: {args.output}")
    
    if not args.quiet:
        print(f"\n{'='*60}")
        print(f"VERIFICATION RESULT: {report.status.value}")
        print(f"EVIDENCE CLASS: {report.evidence_class.value}")
        print(f"{'='*60}")
        print(f"Session ID:       {report.session_id}")
        print(f"Event Count:      {report.event_count}")
        print(f"Chain Authority:  {report.chain_authority}")
        print(f"Verification Mode: {report.verification_mode}")
        print(f"First Hash:       {report.first_event_hash}")
        print(f"Final Hash:       {report.final_event_hash}")
        print(f"\nClassification:   {report.evidence_class_rationale}")
        
        if report.findings:
            print(f"\nFindings ({len(report.findings)}):")
            for f in report.findings:
                print(f"  [{f.severity.value}] {f.finding_type.value}: {f.message}")
        
        print(f"\nExit Code: {report.exit_code}")
    
    sys.exit(report.exit_code)


if __name__ == "__main__":
    main()