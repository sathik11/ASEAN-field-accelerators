"use client";

import React, { useState, useCallback, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { User, Bot, RefreshCw, ChevronDown, ChevronUp } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import ReactMarkdown from "react-markdown";

interface Message {
  content: string;
  role: string;
  name: string;
  isInProgress?: boolean;
}

interface SSEResponse {
  sender: string;
  receiver: string;
  messages: Message[];
}

const exampleMessages = [
  "load https://stgbbaig5yxdataproc.blob.core.windows.net/demo-data/116_ME_Case.pdf and check the occupation",
  "load https://stgbbaig5yxdataproc.blob.core.windows.net/demo-data/116_ExaminerReport_Case.pdf and check the blood pressure",
  "Is there a family medical history",
  "How does blockchain technology work?",
];

export default function MultiAgentChat() {
  const [conversation, setConversation] = useState<SSEResponse | null>(null);
  const [inProgressMessages, setInProgressMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [chatSession, setChatSession] = useState(0);
  const [isMessageListCollapsed, setIsMessageListCollapsed] = useState(true);
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
    }
  }, [conversation, inProgressMessages]);

  const isMessageValid = (message: Message | null): boolean => {
    return (
      message !== null &&
      typeof message.content === "string" &&
      message.content.trim() !== "" &&
      message.name !== "GroupChatManager"
    );
  };

  const handleSendMessage = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (input.trim() && !isLoading) {
        setConversation(null);
        setInProgressMessages([]);
        setInput("");
        setIsLoading(true);

        try {
          const response = await fetch("/api/docprocessor", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question: input }),
          });

          if (!response.ok) throw new Error("Network response was not ok");

          const reader = response.body?.getReader();
          const decoder = new TextDecoder();

          if (reader) {
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
                    let eventData = parsedData.answer || parsedData;

                    if (typeof eventData === "string") {
                      try {
                        eventData = JSON.parse(eventData);
                      } catch (parseError) {
                        console.warn(
                          "Failed to parse eventData as JSON, using it as a string:",
                          parseError
                        );
                        eventData = { content: eventData };
                      }
                    }

                    if (eventData.summary) {
                      setConversation({
                        sender: "System",
                        receiver: "User",
                        messages: [
                          {
                            content: `**Answer:** ${eventData.summary}`,
                            role: "assistant",
                            name: "Multi-Agent",
                          },
                        ],
                      });
                    } else if (eventData.messages) {
                      const messages = Array.isArray(eventData.messages)
                        ? eventData.messages
                        : [{ content: eventData.messages }];
                      const filteredMessages = messages.filter(isMessageValid);
                      setInProgressMessages((prev) => [
                        ...prev,
                        ...filteredMessages.map((msg: Message) => ({
                          content: msg.content,
                          role: msg.role || "assistant",
                          name: msg.name || eventData.sender || "Agent",
                          isInProgress: true,
                        })),
                      ]);
                    } else if (isMessageValid(eventData)) {
                      setInProgressMessages((prev) => [
                        ...prev,
                        {
                          content: eventData.content,
                          role: "assistant",
                          name: eventData.sender || "Agent",
                          isInProgress: true,
                        },
                      ]);
                    }

                    if (eventData.cost) {
                      console.log("Cost information:", eventData.cost);
                    }
                  } catch (error) {
                    console.error("Failed to parse message:", error);
                    console.error("Problematic data:", data);
                  }
                }
              }
            }
          }
        } catch (error) {
          console.error("Error sending message:", error);
          setConversation({
            sender: "System",
            receiver: "User",
            messages: [
              {
                content:
                  "Sorry, there was an error processing your request. Please try again later.",
                role: "assistant",
                name: "System",
              },
            ],
          });
        } finally {
          setIsLoading(false);
        }
      }
    },
    [input, isLoading]
  );

  const handleNewChat = () => {
    setConversation(null);
    setInProgressMessages([]);
    setChatSession((prev) => prev + 1);
  };

  const handleExampleClick = (example: string) => {
    setInput(example);
  };

  const renderMessage = (message: Message) => (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.3 }}
      className="mb-4 last:mb-0"
    >
      <Card
        className={`overflow-hidden ${
          message.isInProgress ? "border-blue-300" : ""
        }`}
      >
        <CardContent className="p-0">
          <div className="flex items-center justify-between bg-muted px-4 py-2">
            <div className="flex items-center space-x-2">
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
              <span className="font-semibold">{message.name}</span>
            </div>
            {message.isInProgress && (
              <span className="text-xs text-blue-500 animate-pulse">
                In Progress
              </span>
            )}
          </div>
          <div className="p-4">
            <div className="prose prose-sm dark:prose-invert max-w-none overflow-hidden">
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );

  return (
    <div className="flex h-[600px] bg-background rounded-lg shadow-lg overflow-hidden">
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
          </div>
        </div>
        <ScrollArea className="flex-grow">
          <div className="p-4 space-y-4" ref={scrollAreaRef}>
            <AnimatePresence>
              {inProgressMessages.length > 0 && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.3 }}
                >
                  <Card>
                    <CardHeader className="py-2">
                      <div className="flex justify-between items-center">
                        <CardTitle className="text-sm">
                          Agent Activities
                        </CardTitle>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() =>
                            setIsMessageListCollapsed(!isMessageListCollapsed)
                          }
                        >
                          {isMessageListCollapsed ? (
                            <ChevronDown className="h-4 w-4" />
                          ) : (
                            <ChevronUp className="h-4 w-4" />
                          )}
                        </Button>
                      </div>
                    </CardHeader>
                    <AnimatePresence>
                      {!isMessageListCollapsed && (
                        <motion.div
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: "auto" }}
                          exit={{ opacity: 0, height: 0 }}
                          transition={{ duration: 0.3 }}
                        >
                          <CardContent>
                            {inProgressMessages
                              .slice(0, -1)
                              .map((message, index) => (
                                <motion.div
                                  key={`${chatSession}-inprogress-${index}`}
                                >
                                  {renderMessage(message)}
                                </motion.div>
                              ))}
                          </CardContent>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </Card>
                </motion.div>
              )}
              {inProgressMessages.length > 0 && (
                <motion.div key={`${chatSession}-latest-message`}>
                  {renderMessage(
                    inProgressMessages[inProgressMessages.length - 1]
                  )}
                </motion.div>
              )}
              {conversation?.messages.map((message, index) => (
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
            <div className="flex flex-wrap gap-2">
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
