"""
AgentOps Replay - LangChain Integration

This module provides automatic instrumentation for LangChain agents,
capturing all LLM calls, tool invocations, and chain execution events
in an audit-grade, verifiable format.

Usage:
    from agentops_replay.integrations.langchain import AgentOpsCallbackHandler
    
    handler = AgentOpsCallbackHandler(
        agent_id="my-agent",
        local_authority=True  # For testing; False for production
    )
    
    # Use with any LangChain component
    llm = ChatOpenAI(callbacks=[handler])
    agent.run("query", callbacks=[handler])
"""

from .callback import AgentOpsCallbackHandler
from .version import INTEGRATION_VERSION, check_compatibility, get_langchain_version

__all__ = [
    "INTEGRATION_VERSION",
    "AgentOpsCallbackHandler",
    "check_compatibility",
    "get_langchain_version"
]
