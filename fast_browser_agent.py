import argparse
import asyncio
import os
import sys
from typing import Optional

from dotenv import load_dotenv

# Speed optimization instructions for the model
SPEED_OPTIMIZATION_PROMPT = (
    """
    Speed optimization instructions:
    - Be extremely concise and direct in your responses
    - Get to the goal as quickly as possible
    - Use multi-action sequences whenever possible to reduce steps
    """
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a speed-optimized browser_use Agent for a given task/query",
    )
    parser.add_argument(
        "task",
        type=str,
        help="Task or query for the agent to execute (e.g., 'summarize latest Rust release notes')",
    )
    parser.add_argument(
        "--provider",
        choices=["groq", "google"],
        default="groq",
        help="LLM provider to use (default: groq)",
    )
    parser.add_argument(
        "--llm-model",
        type=str,
        default=None,
        help=(
            "Override LLM model name. Defaults: "
            "groq='meta-llama/llama-4-maverick-17b-128e-instruct', "
            "google='gemini-flash-lite-latest'"
        ),
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="LLM temperature (default: 0.0)",
    )
    parser.add_argument(
        "--min-wait",
        type=float,
        default=0.1,
        help="Minimum wait for page load time (default: 0.1)",
    )
    parser.add_argument(
        "--wait-between-actions",
        type=float,
        default=0.1,
        help="Wait time between actions (default: 0.1)",
    )
    parser.add_argument(
        "--headless",
        dest="headless",
        action="store_true",
        help="Run browser in headless mode (default)",
    )
    parser.add_argument(
        "--no-headless",
        dest="headless",
        action="store_false",
        help="Run browser with GUI",
    )
    parser.set_defaults(headless=True)
    parser.add_argument(
        "--max-steps",
        type=int,
        default=None,
        help="Optional cap on agent steps (default: unlimited)",
    )
    return parser.parse_args()


async def run_agent(
    task: str,
    provider: str,
    llm_model: Optional[str],
    temperature: float,
    min_wait: float,
    wait_between_actions: float,
    headless: bool,
    max_steps: Optional[int],
) -> None:
    try:
        from browser_use import Agent, BrowserProfile  # type: ignore
    except Exception as exc:  # pragma: no cover
        print(
            "Error: browser_use is not installed or failed to import.\n"
            "Install with: pip install browser-use python-dotenv\n"
            f"Details: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    load_dotenv()

    if provider == "groq":
        try:
            from browser_use import ChatGroq  # type: ignore
        except Exception as exc:  # pragma: no cover
            print(
                "Error: ChatGroq is unavailable. Ensure your browser_use version supports it.",
                f"Details: {exc}",
                file=sys.stderr,
            )
            sys.exit(1)
        if not os.getenv("GROQ_API_KEY"):
            print(
                "Missing GROQ_API_KEY in environment. Set it or use --provider google.",
                file=sys.stderr,
            )
            sys.exit(2)
        model_name = llm_model or "meta-llama/llama-4-maverick-17b-128e-instruct"
        llm = ChatGroq(model=model_name, temperature=temperature)
    else:
        try:
            from browser_use import ChatGoogle  # type: ignore
        except Exception as exc:  # pragma: no cover
            print(
                "Error: ChatGoogle is unavailable. Ensure your browser_use version supports it.",
                f"Details: {exc}",
                file=sys.stderr,
            )
            sys.exit(1)
        if not os.getenv("GOOGLE_API_KEY"):
            print(
                "Missing GOOGLE_API_KEY in environment. Set it or use --provider groq.",
                file=sys.stderr,
            )
            sys.exit(2)
        model_name = llm_model or "gemini-flash-lite-latest"
        llm = ChatGoogle(model=model_name)

    browser_profile = BrowserProfile(
        minimum_wait_page_load_time=min_wait,
        wait_between_actions=wait_between_actions,
        headless=headless,
    )

    agent = Agent(
        task=task,
        llm=llm,
        flash_mode=True,
        browser_profile=browser_profile,
        extend_system_message=SPEED_OPTIMIZATION_PROMPT,
    )

    result = await agent.run(max_steps=max_steps) if max_steps else await agent.run()

    # The returned type can vary by browser_use version; print a readable representation
    try:
        if hasattr(result, "model_dump_json"):
            print(result.model_dump_json())
        elif hasattr(result, "json"):
            print(result.json())
        else:
            print(str(result))
    except Exception:
        print(str(result))


def main() -> None:
    args = parse_args()
    asyncio.run(
        run_agent(
            task=args.task,
            provider=args.provider,
            llm_model=args.llm_model,
            temperature=args.temperature,
            min_wait=args.min_wait,
            wait_between_actions=args.wait_between_actions,
            headless=args.headless,
            max_steps=args.max_steps,
        )
    )


if __name__ == "__main__":
    main()
