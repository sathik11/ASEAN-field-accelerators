"use client";

import React, { useState, useCallback, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { User, Bot, ChevronRight, ChevronLeft, RefreshCw } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import ReactMarkdown from "react-markdown";

// Define types for our messages and initialization steps
type MessageRole = "user" | "assistant";
type MessageStatus = "error" | "success" | "loading";

interface Message {
  role: MessageRole;
  content: string;
  status?: MessageStatus;
  reference?: { name: string; path: string }[];
}

interface InitializationStep {
  type: "initialization";
  title: string;
  content: string;
  files?: { name: string; path: string }[];
}

// Example messages for quick input
const exampleMessages = [
  "Latest OpenAI research openai.com",
  "Responsible AI research microsoft.com",
  "Current Health research news.nih.gov",
  "Travel guidelines https://www.caas.gov.sg/",
];

export default function WebResearcherInterface() {
  // State management
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [initializationSteps, setInitializationSteps] = useState<
    InitializationStep[]
  >([]);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [chatSession, setChatSession] = useState(0);

  // Ref for scroll management
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  // Effect to scroll to bottom when messages change
  useEffect(() => {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
    }
  }, [messages]);

  // Handler for sending messages
  const handleSendMessage = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (input.trim() && !isLoading) {
        // Clear previous messages and steps
        setMessages([]);
        setInitializationSteps([]);

        // Add user message
        const userMessage: Message = { role: "user", content: input };
        setMessages((prev) => [...prev, userMessage]);
        setInput("");
        setIsLoading(true);

        try {
          const response = await fetch("/api/web-researcher", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question: input }),
          });

          if (!response.ok) throw new Error("Network response was not ok");

          const reader = response.body?.getReader();
          const decoder = new TextDecoder();

          if (reader) {
            let assistantMessage: Message | null = null;

            while (true) {
              const { done, value } = await reader.read();
              if (done) break;

              const chunk = decoder.decode(value, { stream: true });
              const lines = chunk.split("\n\n");

              for (const line of lines) {
                if (line.startsWith("data: ")) {
                  const data = line.slice(6);
                  try {
                    const parsedData = JSON.parse(data);
                    const eventData = parsedData.answer
                      ? JSON.parse(parsedData.answer)
                      : parsedData;

                    if (eventData.type === "initialization") {
                      setInitializationSteps((prev) => [...prev, eventData]);
                    } else if (eventData.type === "message") {
                      if (!assistantMessage) {
                        assistantMessage = {
                          role: "assistant",
                          content: eventData.content,
                          status: eventData.status,
                        };
                        setMessages((prev) => [
                          ...prev,
                          assistantMessage as Message,
                        ]);
                      } else {
                        assistantMessage.content += eventData.content;
                        setMessages((prev) =>
                          prev.map((msg, index) =>
                            index === prev.length - 1
                              ? { ...(assistantMessage as Message) }
                              : msg
                          )
                        );
                      }
                    }
                  } catch (error) {
                    console.error("Failed to parse message:", error);
                  }
                }
              }
            }
          }
        } catch (error) {
          console.error("Error sending message:", error);
          const errorMessage: Message = {
            role: "assistant",
            content:
              "Sorry, there was an error processing your request. Please try again later.",
            status: "error",
          };
          setMessages((prev) => [...prev, errorMessage]);
        } finally {
          setIsLoading(false);
        }
      }
    },
    [input, isLoading]
  );

  // Handler for starting a new chat
  const handleNewChat = () => {
    setMessages([]);
    setInitializationSteps([]);
    setChatSession((prev) => prev + 1);
  };

  // Handler for example message clicks
  const handleExampleClick = (example: string) => {
    setInput(example);
  };

  // Function to render individual messages
  const renderMessage = (message: Message) => (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.3 }}
      className="mb-4 last:mb-0"
    >
      <div className="flex items-start gap-3">
        <Avatar>
          <AvatarImage
            src={
              message.role === "user"
                ? "/placeholder-user.jpg"
                : "/placeholder-bot.jpg"
            }
          />
          <AvatarFallback>
            {message.role === "user" ? <User /> : <Bot />}
          </AvatarFallback>
        </Avatar>
        <div className="flex-1 overflow-hidden">
          <div
            className={`p-3 rounded-lg ${
              message.role === "user"
                ? "bg-primary text-primary-foreground"
                : "bg-muted"
            }`}
          >
            {message.role === "user" ? (
              <p className="text-sm whitespace-pre-wrap break-words">
                {message.content}
              </p>
            ) : (
              <div className="prose prose-sm dark:prose-invert max-w-none overflow-hidden">
                <ReactMarkdown>{message.content}</ReactMarkdown>
                {message.reference && (
                  <div className="mt-2">
                    <p className="text-xs font-semibold">References:</p>
                    <ul className="list-disc list-inside">
                      {message.reference.map((ref, index) => (
                        <li key={index} className="text-xs break-words">
                          <a
                            href={ref.path}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            {ref.name}
                          </a>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
          {message.status === "loading" && (
            <div className="mt-2 flex items-center gap-2">
              <div className="animate-pulse bg-muted rounded-full h-2 w-2"></div>
              <div className="animate-pulse bg-muted rounded-full h-2 w-2 animation-delay-200"></div>
              <div className="animate-pulse bg-muted rounded-full h-2 w-2 animation-delay-400"></div>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );

  // Main component render
  return (
    <div className="flex h-[600px] bg-background rounded-lg shadow-lg overflow-hidden">
      <AnimatePresence>
        {isSidebarOpen && (
          <motion.div
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 300, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="border-r"
          >
            <Card className="h-full rounded-none">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle>Research Steps:</CardTitle>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setIsSidebarOpen(false)}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[calc(100vh-10rem)]">
                  {initializationSteps.map((step, index) => (
                    <div key={`${chatSession}-${index}`} className="mb-4">
                      <h3 className="text-sm font-semibold">{step.title}</h3>
                      <p className="text-xs text-muted-foreground break-words">
                        {step.content}
                      </p>
                    </div>
                  ))}
                </ScrollArea>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>
      <div className="flex flex-col flex-grow">
        <div className="p-4 border-b flex justify-between items-center">
          <div className="flex items-center space-x-2">
            <Button
              variant="outline"
              size="icon"
              onClick={handleNewChat}
              title="Start a new chat"
            >
              <RefreshCw className="h-4 w-4" />
              <span className="sr-only">Start a new chat</span>
            </Button>
            {!isSidebarOpen && (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setIsSidebarOpen(true)}
                title="Open agent progress"
              >
                <ChevronRight className="h-4 w-4" />
                <span className="sr-only">Open initialization progress</span>
              </Button>
            )}
          </div>
        </div>
        <ScrollArea className="flex-grow">
          <div className="p-4 space-y-4" ref={scrollAreaRef}>
            <AnimatePresence>
              {messages.map((message, index) => (
                <motion.div key={`${chatSession}-${index}`}>
                  {renderMessage(message)}
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </ScrollArea>
        <div className="p-4 border-t">
          <div className="mb-2">
            <p className="text-sm font-semibold">Examples:</p>
            <div className="flex space-x-2">
              {exampleMessages.map((example, index) => (
                <Button
                  key={index}
                  variant="outline"
                  size="sm"
                  onClick={() => handleExampleClick(example)}
                >
                  {example}
                </Button>
              ))}
            </div>
          </div>
          <form
            onSubmit={handleSendMessage}
            className="flex items-center space-x-2"
          >
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Type your message..."
              disabled={isLoading}
              className="flex-grow"
            />
            <Button type="submit" disabled={isLoading}>
              {isLoading ? "Sending..." : "Send"}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
