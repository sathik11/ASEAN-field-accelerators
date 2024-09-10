import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { atomDark } from "react-syntax-highlighter/dist/esm/styles/prism";

interface MarkdownRendererProps {
  content: string;
}

export function MarkdownRenderer({ content }: MarkdownRendererProps) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        code({ node, inline, className, children, ...props }) {
          const match = /language-(\w+)/.exec(className || "");
          return !inline && match ? (
            <SyntaxHighlighter
              style={atomDark}
              language={match[1]}
              PreTag="div"
              {...props}
              customStyle={{
                margin: 0,
                padding: "1em",
                borderRadius: "0.5em",
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
              }}
            >
              {String(children).replace(/\n$/, "")}
            </SyntaxHighlighter>
          ) : (
            <code className={className} {...props}>
              {children}
            </code>
          );
        },
        p: ({ children }) => <p className="mb-2 break-words">{children}</p>,
        ul: ({ children }) => (
          <ul className="list-disc pl-5 mb-2 break-words">{children}</ul>
        ),
        ol: ({ children }) => (
          <ol className="list-decimal pl-5 mb-2 break-words">{children}</ol>
        ),
        li: ({ children }) => <li className="mb-1 break-words">{children}</li>,
        table: ({ children }) => (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              {children}
            </table>
          </div>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
