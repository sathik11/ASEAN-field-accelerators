"use client";
import React, { useState, useCallback, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { User, Bot } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import InitializationStepper from "./InitializationStepper";

interface Message {
  role: "user" | "assistant";
  content: string;
  status?: "error" | "success" | "loading";
}

interface InitializationStep {
  type: "initialization";
  title: string;
  content: string;
  files?: { name: string; path: string }[];
}

interface ChatInterfaceProps {
  botId: string;
}

export default function ChatInterface({ botId }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [initializationSteps, setInitializationSteps] = useState<
    InitializationStep[]
  >([]);
  const [currentStep, setCurrentStep] = useState(0);
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
    }
  }, [messages, initializationSteps]);

  const handleSendMessage = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (input.trim() && !isLoading) {
        const userMessage: Message = { role: "user", content: input };
        setMessages((prev) => [...prev, userMessage]);
        setInput("");
        setIsLoading(true);

        try {
          const response = await fetch(`/api/${botId}`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ question: input }),
          });

          if (!response.ok) {
            throw new Error("Network response was not ok");
          }

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
                    const answerData = JSON.parse(parsedData.answer);

                    if (answerData.type === "initialization") {
                      setInitializationSteps((prev) => [...prev, answerData]);
                      setCurrentStep((prev) => prev + 1);
                    } else if (answerData.type === "message") {
                      if (!assistantMessage) {
                        assistantMessage = {
                          role: "assistant",
                          content: answerData.content,
                          status: answerData.status,
                        };
                        setMessages((prev) => [...prev, assistantMessage]);
                      } else {
                        assistantMessage.content += answerData.content;
                        setMessages((prev) => [
                          ...prev.slice(0, -1),
                          assistantMessage,
                        ]);
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
    [input, isLoading, botId]
  );

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
        <div className="flex-1">
          <div
            className={`p-3 rounded-lg ${
              message.role === "user"
                ? "bg-primary text-primary-foreground"
                : "bg-muted"
            }`}
          >
            <p className="text-sm whitespace-pre-wrap">{message.content}</p>
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

  return (
    <div className="flex flex-col h-[600px] bg-background rounded-lg shadow-lg">
      <div className="p-4 border-b">
        <h2 className="text-xl font-bold">GenAI Chatbot Showcase</h2>
      </div>
      <ScrollArea className="flex-grow p-4" ref={scrollAreaRef}>
        {initializationSteps.length > 0 && (
          <InitializationStepper
            steps={initializationSteps}
            currentStep={currentStep}
          />
        )}
        <AnimatePresence>
          {messages.map((message, index) => (
            <motion.div key={index}>{renderMessage(message)}</motion.div>
          ))}
        </AnimatePresence>
      </ScrollArea>
      <form
        onSubmit={handleSendMessage}
        className="p-4 border-t flex items-center space-x-2"
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
  );
}
