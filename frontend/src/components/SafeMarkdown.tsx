import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";

export type SafeMarkdownProps = {
  content: string;
  className?: string;
};

// Very conservative schema: rely on defaultSchema and allow common markdown tags.
// Do NOT allow style or event handlers; keep links/images constrained.
const schema = (() => {
  const s: any = { ...defaultSchema };
  s.tagNames = Array.from(new Set([...
    (defaultSchema as any).tagNames,
    "p","br","hr","blockquote","code","pre","em","strong","kbd","samp",
    "ul","ol","li","a","img","table","thead","tbody","tr","th","td",
    "h1","h2","h3","h4","h5","h6"
  ]));
  s.attributes = {
    ...(defaultSchema as any).attributes,
    a: ["href", "title", "rel", "target"],
    img: ["src", "alt", "title", "width", "height"],
    code: ["className"],
    pre: []
  };
  // Limit URL protocols on links and images
  s.protocols = {
    ...(defaultSchema as any).protocols,
    href: ["http", "https", "mailto", "tel"],
    src: ["http", "https", "data"] // data URLs allowed for inline images only
  };
  return s;
})();

export const SafeMarkdown: React.FC<SafeMarkdownProps> = ({ content, className }) => {
  return (
    <div className={className}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw, [rehypeSanitize, schema]]}
        components={{
          a: ({node, ...props}) => (
            <a
              {...props}
              target="_blank"
              rel="noopener noreferrer nofollow"
              className="text-primary underline underline-offset-2"
            />
          ),
          code: ({children, ...props}) => (
            <code className="rounded bg-muted px-1 py-0.5 text-sm font-mono" {...props}>
              {children}
            </code>
          ),
          img: ({node, ...props}) => (
            // Disallow onError/onLoad etc; only safe attributes are forwarded by sanitize
            <img loading="lazy" decoding="async" className="max-w-full" {...props} />
          ),
          table: ({node, ...props}) => (
            <div className="my-3 w-full overflow-x-auto">
              <table className="w-full text-sm" {...props} />
            </div>
          ),
          blockquote: ({node, ...props}) => (
            <blockquote className="border-l-4 border-border pl-3 italic text-muted-foreground" {...props} />
          )
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};

export default SafeMarkdown;

