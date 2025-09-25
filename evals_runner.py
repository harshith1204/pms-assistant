import asyncio
import os
from typing import List, Dict, Any

from observability.langfuse import langfuse_obs
from agent import MongoDBAgent


async def run_eval_cases(cases: List[str]) -> List[Dict[str, Any]]:
    agent = MongoDBAgent()
    await agent.connect()

    results: List[Dict[str, Any]] = []
    for idx, prompt in enumerate(cases, 1):
        trace_name = f"eval_case_{idx}"
        client = langfuse_obs.client()
        trace = client.trace(name=trace_name) if client else None

        try:
            output = await agent.run(prompt)
            item = {
                "index": idx,
                "prompt": prompt,
                "output": output,
            }
            results.append(item)
            if trace:
                trace.generation(
                    name="agent_run",
                    input=prompt,
                    output=output,
                    model="ollama:qwen3",
                )
        except Exception as e:
            results.append({"index": idx, "prompt": prompt, "error": str(e)})
            if trace:
                trace.event(name="error", input=prompt, metadata={"error": str(e)})

        if trace:
            trace.end()

    return results


async def main():
    dataset_path = os.getenv("EVAL_DATASET", "/workspace/test_dataset.txt")
    cases: List[str] = []
    if os.path.exists(dataset_path):
        with open(dataset_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.lower().startswith("questions"):
                    continue
                cases.append(line)

    results = await run_eval_cases(cases)
    print(f"Ran {len(results)} eval cases")
    # Optionally, compute simple metrics
    num_errors = sum(1 for r in results if "error" in r)
    print(f"Errors: {num_errors}")


if __name__ == "__main__":
    asyncio.run(main())

