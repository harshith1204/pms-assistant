from __future__ import annotations

import asyncio
import os
import sys
from typing import Optional

from dotenv import load_dotenv

# Update this task string to change what the agent does
TASK: str = (
    """
    1. Go to reddit https://www.reddit.com/search/?q=browser+agent&type=communities
    2. Click directly on the first 5 communities to open each in new tabs
    3. Find out what the latest post is about, and switch directly to the next tab
    4. Return the latest post summary for each page
    """
)

# Speed optimization prompt injected into the agent's system message
SPEED_OPTIMIZATION_PROMPT: str = (
    """
    Speed optimization instructions:
    - Be extremely concise and direct in your responses
    - Get to the goal as quickly as possible
    - Use multi-action sequences whenever possible to reduce steps
    """
)

# Fast defaults (edit as needed)
LLM_MODEL: str = "meta-llama/llama-4-maverick-17b-128e-instruct"
LLM_TEMPERATURE: float = 0.0
MINIMUM_WAIT_PAGE_LOAD_TIME: float = 0.1
WAIT_BETWEEN_ACTIONS: float = 0.1
HEADLESS: bool = True
MAX_STEPS: Optional[int] = 8  # set to None for unlimited


def _stringify_result(result: object) -> str:
    """Return a readable string from various result shapes across browser_use versions."""
    try:
        for attr in ("final_result", "result", "text", "content"):
            if hasattr(result, attr):
                value = getattr(result, attr)
                if callable(value):
                    try:
                        value = value()
                    except Exception:
                        pass
                if isinstance(value, (str, int, float)):
                    return str(value)
        # Pydantic-like
        if hasattr(result, "model_dump_json"):
            return result.model_dump_json()  # type: ignore[attr-defined]
        if hasattr(result, "json"):
            return result.json()  # type: ignore[attr-defined]
    except Exception:
        pass
    return str(result)


async def _run() -> None:
    load_dotenv()

    if not os.getenv("GROQ_API_KEY"):
        print(
            "Missing GROQ_API_KEY in environment. Set it before running.",
            file=sys.stderr,
        )
        sys.exit(2)

    try:
        from browser_use import Agent, BrowserProfile, ChatGroq  # type: ignore
    except Exception as exc:
        print(
            "Error: browser_use is not installed or failed to import.\n"
            "Install with: pip install browser-use python-dotenv\n"
            f"Details: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    llm = ChatGroq(model=LLM_MODEL, temperature=LLM_TEMPERATURE)

    browser_profile = BrowserProfile(
        minimum_wait_page_load_time=MINIMUM_WAIT_PAGE_LOAD_TIME,
        wait_between_actions=WAIT_BETWEEN_ACTIONS,
        headless=HEADLESS,
    )

    agent = Agent(
        task=TASK,
        llm=llm,
        flash_mode=True,
        browser_profile=browser_profile,
        extend_system_message=SPEED_OPTIMIZATION_PROMPT,
    )

    result = await agent.run(max_steps=MAX_STEPS) if MAX_STEPS else await agent.run()
    print(_stringify_result(result))


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
