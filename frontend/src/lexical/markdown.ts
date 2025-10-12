import { TRANSFORMERS } from "@lexical/markdown";

// Central place to customize supported Markdown features for Lexical.
// Start from Lexical defaults; add or remove transformers here as needed.
// Example (when you want to customize):
// export const MARKDOWN_TRANSFORMERS = TRANSFORMERS.filter(t => t.__name !== 'CODE');
// For now, keep defaults and iterate based on product needs.
export const MARKDOWN_TRANSFORMERS: ReadonlyArray<any> = TRANSFORMERS;
