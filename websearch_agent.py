"""
WebSearchAgent: Fast web search + parallel subtask execution using ChatGroq and (optionally) browser-use.

Quick start
- Set environment: export GROQ_API_KEY=...  (required)
- Install deps: pip install -r requirements.txt
- Install Playwright browsers (only if you want browser-use rendering): python -m playwright install --with-deps
- Run:
  python websearch_agent.py "Summarize latest Rust release notes and key changes"

What it does
- Plans 2-5 independent subtasks with ChatGroq
- For each subtask, runs a fast DuckDuckGo search and fetches top N pages in parallel
- Optionally uses browser-use + Playwright to render one page per subtask (JS-heavy) when available
- Synthesizes a concise answer with sources using ChatGroq

Environment variables
- GROQ_MODEL (default: llama-3.1-8b-instant)
- GROQ_TEMPERATURE (default: 0.1)
- GROQ_MAX_TOKENS (default: 1024)

Notes
- browser-use is optional; HTTP fetch + BeautifulSoup is used by default for speed.
- If you need deeper browsing actions (logins, navigation), switch more URLs to the browser-use path.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import textwrap
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

# Optional imports: browser-use + DuckDuckGo search
BROWSER_USE_AVAILABLE = False
try:
    from browser_use import Agent as BrowserAgent  # type: ignore
    from browser_use import Browser as BrowserUseBrowser  # type: ignore
    from browser_use import BrowserConfig as BrowserUseConfig  # type: ignore
    BROWSER_USE_AVAILABLE = True
except Exception:
    BROWSER_USE_AVAILABLE = False

try:
    from duckduckgo_search import DDGS  # type: ignore
    DUCK_AVAILABLE = True
except Exception:
    DUCK_AVAILABLE = False

load_dotenv()


def create_llm() -> ChatGroq:
    return ChatGroq(
        model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
        temperature=float(os.getenv("GROQ_TEMPERATURE", "0.1")),
        max_tokens=int(os.getenv("GROQ_MAX_TOKENS", "1024")),
        streaming=False,
        verbose=False,
        top_p=0.8,
    )


@dataclass
class Subtask:
    title: str
    query: str


class WebSearchAgent:
    """Planner + parallel web fetcher using ChatGroq and optional browser-use rendering."""

    def __init__(
        self,
        max_subtasks: int = 4,
        per_task_results: int = 2,
        request_timeout_seconds: int = 15,
        enable_browser_use: bool = True,
    ) -> None:
        if max_subtasks < 1:
            raise ValueError("max_subtasks must be >= 1")
        if per_task_results < 1:
            raise ValueError("per_task_results must be >= 1")

        self.llm = create_llm()
        self.max_subtasks = min(max_subtasks, 6)
        self.per_task_results = min(per_task_results, 5)
        self.request_timeout_seconds = request_timeout_seconds
        self.enable_browser_use = enable_browser_use and BROWSER_USE_AVAILABLE

        # Single shared async client for HTTP fetch
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=self.request_timeout_seconds, follow_redirects=True)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._client:
            await self._client.aclose()
        self._client = None

    async def run(self, user_task: str) -> Dict[str, Any]:
        subtasks = await self._plan_subtasks(user_task)
        if not subtasks:
            subtasks = [Subtask(title="Primary search", query=user_task)]

        # Parallel execution of subtasks
        subtask_results = await asyncio.gather(*[
            self._execute_subtask(st) for st in subtasks[: self.max_subtasks]
        ])

        # Flatten contents and keep best snippets
        findings: List[Tuple[str, str, str]] = []  # (subtask_title, url, snippet)
        for st, results in zip(subtasks, subtask_results):
            for url, snippet in results:
                findings.append((st.title, url, snippet))

        # Deduplicate URLs while preserving order
        seen: set[str] = set()
        unique_findings: List[Tuple[str, str, str]] = []
        for st_title, url, snippet in findings:
            if url not in seen and snippet.strip():
                unique_findings.append((st_title, url, snippet))
                seen.add(url)

        concise_answer = await self._synthesize(user_task, unique_findings)

        sources = [url for _, url, _ in unique_findings][:10]
        return {
            "answer": concise_answer.strip(),
            "sources": sources,
            "subtasks": [st.__dict__ for st in subtasks],
        }

    async def _plan_subtasks(self, user_task: str) -> List[Subtask]:
        """Use ChatGroq to produce 2-5 independent, parallelizable subtasks in JSON."""
        sys_msg = SystemMessage(content=
            "Plan 2-5 brief, independent subtasks for fast web research. "
            "Each subtask must be a self-contained search query. Return strict JSON: "
            "{\"subtasks\":[{\"title\":str,\"query\":str}, ...]}"
        )
        human = HumanMessage(content=f"Task: {user_task}\nReturn only JSON, no prose.")
        try:
            resp = await self.llm.ainvoke([sys_msg, human])
            content = (getattr(resp, "content", "") or "").strip()
            data = json.loads(content)
            items = data.get("subtasks", [])
        except Exception:
            # Fallback simple breakdown if LLM JSON fails
            items = [
                {"title": "Official sources", "query": f"site:official {user_task}"},
                {"title": "News coverage", "query": f"news {user_task}"},
                {"title": "Community insights", "query": f"reddit or stackoverflow {user_task}"},
            ]

        subtasks: List[Subtask] = []
        for item in items[:5]:
            title = str(item.get("title") or "Search").strip()[:80]
            query = str(item.get("query") or user_task).strip()[:240]
            if query:
                subtasks.append(Subtask(title=title, query=query))
        return subtasks[: max(1, self.max_subtasks)]

    async def _execute_subtask(self, st: Subtask) -> List[Tuple[str, str]]:
        """Search and fetch content for a subtask in parallel. Returns list[(url, snippet)]."""
        urls = await self._search_urls(st.query, self.per_task_results)
        if not urls:
            return []

        # For speed: HTTP fetch all URLs concurrently; optionally render one via browser-use
        results: List[Tuple[str, str]] = []
        sem = asyncio.Semaphore(6)

        async def fetch_with_sem(u: str) -> Tuple[str, str]:
            async with sem:
                return await self._fetch_snippet(u)

        tasks = [fetch_with_sem(u) for u in urls]
        snippets = await asyncio.gather(*tasks, return_exceptions=True)

        for u, s in zip(urls, snippets):
            if isinstance(s, Exception):
                continue
            results.append((u, s))

        # Optionally replace the first result with a browser-use-rendered snippet if available
        if self.enable_browser_use and results:
            try:
                rendered_snip = await self._render_snippet_with_browser_use(results[0][0])
                if rendered_snip and len(rendered_snip) > len(results[0][1]):
                    results[0] = (results[0][0], rendered_snip)
            except Exception:
                pass

        return results

    async def _search_urls(self, query: str, limit: int) -> List[str]:
        if DUCK_AVAILABLE:
            try:
                with DDGS(timeout=self.request_timeout_seconds) as ddgs:  # type: ignore
                    results = list(ddgs.text(query, max_results=limit))  # type: ignore
                urls = [r.get("href") or r.get("url") or "" for r in results]
                return [u for u in urls if u]
            except Exception:
                pass
        # Basic fallback if DDG library missing/fails
        return [f"https://duckduckgo.com/?q={httpx.utils.quote(query)}"]

    async def _fetch_snippet(self, url: str) -> Tuple[str, str]:
        if not self._client:
            self._client = httpx.AsyncClient(timeout=self.request_timeout_seconds, follow_redirects=True)
        try:
            resp = await self._client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                               "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
            })
            text = self._extract_text(resp.text)
            snippet = self._clean_snippet(text)[:2000]
            if snippet:
                return url, snippet
        except Exception:
            pass
        return url, ""

    async def _render_snippet_with_browser_use(self, url: str) -> str:
        if not BROWSER_USE_AVAILABLE:
            return ""
        # Minimal usage; concrete APIs may vary by browser-use version
        try:
            browser = BrowserUseBrowser(BrowserUseConfig(headless=True))
            agent = BrowserAgent(
                task=f"Open {url} and extract the main textual content. Return 8-12 bullet points summarizing the key facts.",
                browser=browser,
                llm=create_llm(),
            )
            result = await agent.run()
            # Many versions return a pydantic model with a .result or .final_result attribute
            summary = getattr(result, "result", None) or getattr(result, "final_result", None) or str(result)
            return self._clean_snippet(str(summary))[:3000]
        except Exception:
            return ""

    async def _synthesize(self, user_task: str, findings: List[Tuple[str, str, str]]) -> str:
        """Ask ChatGroq to synthesize a concise answer grounded in the collected snippets."""
        if not findings:
            return "No reliable results found. Try a more specific query."

        # Build a compact, cited context
        bullets: List[str] = []
        for idx, (_, url, snippet) in enumerate(findings[:12], start=1):
            short_url = self._shorten_url(url)
            bullets.append(f"[{idx}] {short_url}: {snippet[:600]}")
        context = "\n".join(bullets)

        sys_msg = SystemMessage(content=textwrap.dedent(
            f"""
            You are a fast web researcher. Write a concise answer (5-9 sentences) to the user task
            grounded only in the context snippets. Prefer facts that appear across multiple sources.
            Include a short 'Sources' list of the most relevant 3-6 URLs. Avoid fluff.
            """
        ).strip())
        human = HumanMessage(content=textwrap.dedent(
            f"""
            Task: {user_task}

            Context snippets with numbered sources:\n{context}

            Write the answer followed by a 'Sources' list using the numbered citations.
            """
        ).strip())
        try:
            resp = await self.llm.ainvoke([sys_msg, human])
            return (getattr(resp, "content", "") or "").strip()
        except Exception:
            # Minimal fallback when LLM fails
            lines = [f"- {self._shorten_url(u)}" for _, u, _ in findings[:5]]
            return "\n".join(["Here are useful sources:", *lines])

    @staticmethod
    def _extract_text(html: str) -> str:
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "noscript", "template", "svg", "img"]):
            tag.decompose()
        # Prefer meta description + h1/h2 + paragraphs
        parts: List[str] = []
        desc = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
        if desc and desc.get("content"):
            parts.append(desc["content"])  # type: ignore[index]
        title_el = soup.find("h1") or soup.find("title")
        if title_el and title_el.get_text(" ", strip=True):
            parts.append(title_el.get_text(" ", strip=True))
        headings = [h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2"])][:6]
        parts.extend([h for h in headings if h])
        paras = [p.get_text(" ", strip=True) for p in soup.find_all("p")][:30]
        parts.extend([p for p in paras if p])
        text = " \n".join(parts)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _clean_snippet(text: str) -> str:
        text = re.sub(r"\s+", " ", text).strip()
        # Drop very short or cookie-banners-like content
        if len(text) < 60:
            return ""
        return text

    @staticmethod
    def _shorten_url(url: str) -> str:
        try:
            return re.sub(r"^https?://(www\.)?", "", url).rstrip("/")[:80]
        except Exception:
            return url[:80]


async def _amain(args: argparse.Namespace) -> int:
    async with WebSearchAgent(
        max_subtasks=args.max_subtasks,
        per_task_results=args.per_task_results,
        request_timeout_seconds=args.timeout,
        enable_browser_use=not args.no_browser_use,
    ) as agent:
        result = await agent.run(args.task)

    print(result["answer"])  # concise answer first
    if result.get("sources"):
        print("\nSources:")
        for u in result["sources"]:
            print(f"- {u}")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fast websearch agent using ChatGroq and browser-use")
    parser.add_argument("task", type=str, help="User task or question to research")
    parser.add_argument("--max-subtasks", type=int, default=4, help="Max number of planned subtasks (1-6)")
    parser.add_argument("--per-task-results", type=int, default=2, help="Top N URLs per subtask (1-5)")
    parser.add_argument("--timeout", type=int, default=15, help="HTTP request timeout seconds")
    parser.add_argument("--no-browser-use", action="store_true", help="Disable browser-use rendering path")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        asyncio.run(_amain(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
