"use server";

import { NextResponse } from "next/server";
import { createParser } from "eventsource-parser";

const API_ENDPOINTS = {
  "web-researcher": {
    url: "http://localhost:8083/score",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
  },
};

interface Message {
  status: "success" | "error" | "in_progress";
  message: string;
  details: Record<string, any>;
}

export async function sendMessage(
  botId: string,
  message: string
): Promise<Message[]> {
  const apiConfig = API_ENDPOINTS[botId as keyof typeof API_ENDPOINTS];

  if (!apiConfig) {
    throw new Error("Invalid bot ID");
  }

  const messages: Message[] = [];

  try {
    const response = await fetch(apiConfig.url, {
      method: "POST",
      headers: {
        ...apiConfig.headers,
        Accept: "text/event-stream",
      },
      body: JSON.stringify({ question: message, test: false }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    const parser = createParser((event) => {
      if (event.type === "event") {
        try {
          const outerData = JSON.parse(event.data);
          const innerData = JSON.parse(outerData.answer);
          const msg: Message = {
            status: innerData.status || "in_progress",
            message: innerData.message || "",
            details: innerData.details || {},
          };
          messages.push(msg);
        } catch (error) {
          console.error("Error parsing SSE data:", error);
        }
      }
    });

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      parser.feed(decoder.decode(value, { stream: true }));
    }
  } catch (error) {
    console.error("Error calling external API:", error);
    throw new Error("Failed to get response from the AI service");
  }

  return messages;
}
