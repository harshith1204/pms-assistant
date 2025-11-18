import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Strip common markdown formatting characters from text for display purposes
 */
export function stripMarkdown(text: string): string {
  if (!text) return text;

  return text
    // Remove headers (# ## ###)
    .replace(/^#{1,6}\s+/gm, '')
    // Remove bold/italic markers (* ** _ __)
    .replace(/(\*\*|__|\*|_)(.*?)\1/g, '$2')
    // Remove inline code (`)
    .replace(/`([^`]+)`/g, '$1')
    // Remove code blocks (```...```)
    .replace(/```[\s\S]*?```/g, '')
    // Remove links ([text](url))
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    // Remove images (![alt](url))
    .replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1')
    // Remove strikethrough (~~text~~)
    .replace(/~~(.*?)~~/g, '$1')
    // Remove blockquotes (>)
    .replace(/^>\s+/gm, '')
    // Remove list markers (- * +)
    .replace(/^[-*+]\s+/gm, '')
    // Remove numbered lists (1. 2. etc)
    .replace(/^\d+\.\s+/gm, '')
    // Clean up extra whitespace
    .replace(/\s+/g, ' ')
    .trim();
}
