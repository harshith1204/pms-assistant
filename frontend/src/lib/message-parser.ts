/**
 * Parse think tags from LLM responses and extract them as separate thoughts
 */

export interface ParsedMessage {
  mainContent: string;
  thoughts: string[];
}

/**
 * Parses content to extract think tags and returns cleaned content with separate thoughts
 * @param content The raw content that may contain <think> tags
 * @returns Object containing main content without think tags and array of extracted thoughts
 */
export function parseThinkTags(content: string): ParsedMessage {
  const thoughts: string[] = [];
  
  // Regular expression to match <think> content </think> tags (including newlines)
  const thinkTagRegex = /<think>([\s\S]*?)<\/think>/gi;
  
  // Extract all think tag contents
  let match;
  while ((match = thinkTagRegex.exec(content)) !== null) {
    const thoughtContent = match[1].trim();
    if (thoughtContent) {
      thoughts.push(thoughtContent);
    }
  }
  
  // Remove all think tags from the content
  const mainContent = content
    .replace(thinkTagRegex, '')
    .trim();
  
  return {
    mainContent,
    thoughts
  };
}

/**
 * Check if a string contains think tags
 * @param content The content to check
 * @returns true if content contains think tags
 */
export function hasThinkTags(content: string): boolean {
  return /<think>[\s\S]*?<\/think>/i.test(content);
}