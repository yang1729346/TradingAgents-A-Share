from abc import ABC, abstractmethod
import re
from typing import Any, Optional
import warnings
import uuid


_FUNC_CALL_RE = re.compile(
    r"<function=(\w+?)>(.*?)</\s*function>",
    re.DOTALL,
)
_PARAM_RE = re.compile(
    r"<parameter=(\w+?)>(.*?)</parameter>",
    re.DOTALL,
)
_PARAM_RE2 = re.compile(
    r"<parameter=(\w+?)>(.*?)(?=<(?:parameter|/function|function=)|$)",
    re.DOTALL,
)


def _parse_xml_tool_calls(content):
    calls = []
    for match in _FUNC_CALL_RE.finditer(content):
        func_name = match.group(1)
        body = match.group(2)
        args = {}
        for m in _PARAM_RE.finditer(body):
            args[m.group(1)] = m.group(2).strip()
        if not args:
            for m in _PARAM_RE2.finditer(body):
                args[m.group(1)] = m.group(2).strip()
        calls.append({
"name": func_name,
"args": args,
"id": f"call_{uuid.uuid4().hex[:24]}",
"type": "tool_call",
        })
    return calls


def normalize_content(response):
    """Normalize LLM response and recover XML tool calls."""
    content = response.content
    if isinstance(content, list):
        texts = [
            item.get("text", "") if isinstance(item, dict) and item.get("type") == "text"
            else item if isinstance(item, str) else ""
            for item in content
        ]
        response.content = "\n".join(t for t in texts if t)

    if not response.tool_calls and isinstance(response.content, str):
        xml_calls = _parse_xml_tool_calls(response.content)
        if xml_calls:
            response.tool_calls = xml_calls
            cleaned = _FUNC_CALL_RE.sub("", response.content).strip()
            response.content = cleaned

    return response


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""

    def __init__(self, model: str, base_url: Optional[str] = None, **kwargs):
        self.model = model
        self.base_url = base_url
        self.kwargs = kwargs

    def get_provider_name(self) -> str:
        provider = getattr(self, "provider", None)
        if provider:
            return str(provider)
        return self.__class__.__name__.removesuffix("Client").lower()

    def warn_if_unknown_model(self) -> None:
        if self.validate_model():
            return
        warnings.warn(
            (
                f"Model '{self.model}' is not in the known model list for "
                f"provider '{self.get_provider_name()}'. Continuing anyway."
            ),
            RuntimeWarning,
            stacklevel=2,
        )

    @abstractmethod
    def get_llm(self) -> Any:
        pass

    @abstractmethod
    def validate_model(self) -> bool:
        pass
