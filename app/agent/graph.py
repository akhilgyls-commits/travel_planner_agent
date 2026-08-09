"""
LangGraph agent definition.

Uses LangGraph's prebuilt `create_react_agent`, which implements the
classic reason -> act (tool call) -> observe loop as a compiled graph.
A `MemorySaver` checkpointer gives us short-term conversational memory
keyed by `thread_id` (== our `session_id`), so follow-up questions
naturally have access to prior turns without us re-sending full history
manually.
"""
from typing import Any, Dict, List

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from app.agent.llm import build_chat_model
from app.agent.prompts import SYSTEM_PROMPT
from app.config import get_settings
from app.logging_config import get_logger
from app.tools import ALL_TOOLS

logger = get_logger(__name__)


class TravelAgent:
    """
    Thin wrapper around a compiled LangGraph agent that adds:
      - a fixed system prompt
      - conversation memory via checkpointing
      - convenience methods for the FastAPI layer
      - tool-usage tracking for observability/response metadata
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._checkpointer = MemorySaver()
        self._llm = build_chat_model(settings)
        self._graph = create_react_agent(
            model=self._llm,
            tools=ALL_TOOLS,
            checkpointer=self._checkpointer,
        )

    def _invoke(self, session_id: str, user_message: str, include_system: bool) -> Dict[str, Any]:
        config = {"configurable": {"thread_id": session_id}}
        messages: List[BaseMessage] = []
        if include_system:
            messages.append(SystemMessage(content=SYSTEM_PROMPT))
        messages.append(HumanMessage(content=user_message))

        logger.info(
            "agent.invoke",
            extra={"session_id": session_id, "message_preview": user_message[:120]},
        )

        result = self._graph.invoke({"messages": messages}, config=config)
        final_messages: List[BaseMessage] = result["messages"]

        answer = ""
        tools_used: List[str] = []
        for msg in final_messages:
            if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
                tools_used.extend(tc["name"] for tc in msg.tool_calls)
            if isinstance(msg, AIMessage) and msg.content:
                answer = msg.content if isinstance(msg.content, str) else str(msg.content)

        return {"answer": answer, "tools_used": list(dict.fromkeys(tools_used))}

    def plan_trip(self, session_id: str, planning_prompt: str) -> Dict[str, Any]:
        """First turn of a session: includes the system prompt."""
        return self._invoke(session_id, planning_prompt, include_system=True)

    def ask_followup(self, session_id: str, question: str) -> Dict[str, Any]:
        """Subsequent turns: memory (checkpointer) already has system + history."""
        return self._invoke(session_id, question, include_system=False)

    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        """Read back the conversation history for a session, human-readable."""
        config = {"configurable": {"thread_id": session_id}}
        state = self._graph.get_state(config)
        if not state or "messages" not in state.values:
            return []

        history = []
        for msg in state.values["messages"]:
            if isinstance(msg, SystemMessage):
                continue
            if isinstance(msg, HumanMessage):
                history.append({"role": "user", "content": str(msg.content)})
            elif isinstance(msg, AIMessage) and msg.content:
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                history.append({"role": "assistant", "content": content})
        return history

    def session_exists(self, session_id: str) -> bool:
        config = {"configurable": {"thread_id": session_id}}
        state = self._graph.get_state(config)
        return bool(state and state.values.get("messages"))


_agent_singleton: TravelAgent | None = None


def get_travel_agent() -> TravelAgent:
    """Lazily construct the agent once per process (holds LLM client + checkpointer)."""
    global _agent_singleton
    if _agent_singleton is None:
        _agent_singleton = TravelAgent()
    return _agent_singleton
