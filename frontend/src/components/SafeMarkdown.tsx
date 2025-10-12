import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";

export type SafeMarkdownProps = {
  content: string;
  className?: string;
  inline?: boolean;
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

export const SafeMarkdown: React.FC<SafeMarkdownProps> = ({ content, className, inline = false }) => {
  const commonComponents = {
    a: ({ node, ...props }: any) => (
      <a
        {...props}
        target="_blank"
        rel="noopener noreferrer nofollow"
        className="text-primary underline underline-offset-2"
      />
    ),
    code: ({ children, ...props }: any) => (
      <code className="rounded bg-muted px-1 py-0.5 text-sm font-mono" {...props}>
        {children}
      </code>
    ),
    img: ({ node, ...props }: any) => (
      // Disallow onError/onLoad etc; only safe attributes are forwarded by sanitize
      <img loading="lazy" decoding="async" className="max-w-full" {...props} />
    ),
    table: ({ node, ...props }: any) => (
      <div className="my-3 w-full overflow-x-auto">
        <table className="w-full text-sm" {...props} />
      </div>
    ),
    blockquote: ({ node, ...props }: any) => (
      <blockquote className="border-l-4 border-border pl-3 italic text-muted-foreground" {...props} />
    )
  } as const;

  if (inline) {
    return (
      <span className={className}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeRaw, [rehypeSanitize, schema]]}
          // Restrict to inline-safe elements and render paragraphs as spans
          allowedElements={["p", "em", "strong", "code", "a", "br", "kbd", "samp"]}
          components={{
            ...commonComponents,
            p: ({ children, ...props }: any) => <span {...props}>{children}</span>
          }}
        >
          {content}
        </ReactMarkdown>
      </span>
    );
  }

  return (
    <div className={className}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw, [rehypeSanitize, schema]]}
        components={commonComponents as any}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};

export default SafeMarkdown;

