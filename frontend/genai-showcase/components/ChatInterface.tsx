"use client";

import { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { sendMessage } from "@/app/actions";
import { Loader2 } from "lucide-react";

interface Message {
  role: "user" | "assistant";
  content: string;
  status?: "success" | "error" | "in_progress";
  details?: Record<string, any>;
}

interface ChatInterfaceProps {
  botId: string;
}

export default function ChatInterface({ botId }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [streamingMessage, setStreamingMessage] = useState<Message | null>(
    null
  );
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
    }
  }, [messages, streamingMessage]);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      const userMessage: Message = { role: "user", content: input };
      setMessages((prev) => [...prev, userMessage]);
      setInput("");
      setIsLoading(true);
      setStreamingMessage(null);

      try {
        const response = await sendMessage(botId, input);

        for await (const msg of response) {
          setStreamingMessage((prev) => ({
            role: "assistant",
            content: prev ? prev.content + msg.message : msg.message,
            status: msg.status,
            details: msg.details,
          }));
        }

        setMessages((prev) => [...prev, streamingMessage!]);
        setStreamingMessage(null);
      } catch (error) {
        console.error("Error sending message:", error);
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content:
              "Sorry, there was an error processing your request. Please try again later.",
            status: "error",
          },
        ]);
      } finally {
        setIsLoading(false);
      }
    }
  };

  const renderMessage = (message: Message) => (
    <div
      className={`flex items-start space-x-2 ${
        message.role === "user" ? "flex-row-reverse" : ""
      }`}
    >
      <Avatar>
        <AvatarFallback>{message.role === "user" ? "U" : "A"}</AvatarFallback>
      </Avatar>
      <div
        className={`p-2 rounded-lg ${
          message.role === "user"
            ? "bg-primary text-primary-foreground"
            : message.status === "error"
            ? "bg-destructive text-destructive-foreground"
            : "bg-muted"
        }`}
      >
        {message.content}
        {message.status === "in_progress" && (
          <Loader2 className="h-4 w-4 animate-spin inline-block ml-2" />
        )}
      </div>
    </div>
  );

  return (
    <div className="flex flex-col h-[600px]">
      <ScrollArea className="flex-grow p-4 space-y-4" ref={scrollAreaRef}>
        {messages.map((message, index) => (
          <div
            key={index}
            className={`flex ${
              message.role === "user" ? "justify-end" : "justify-start"
            }`}
          >
            {renderMessage(message)}
          </div>
        ))}
        {streamingMessage && (
          <div className="flex justify-start">
            {renderMessage(streamingMessage)}
          </div>
        )}
      </ScrollArea>
      <form onSubmit={handleSendMessage} className="flex space-x-2 p-4">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your message..."
          className="flex-grow"
          disabled={isLoading}
        />
        <Button type="submit" disabled={isLoading}>
          {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Send"}
        </Button>
      </form>
    </div>
  );
}
