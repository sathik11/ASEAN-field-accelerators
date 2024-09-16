"use client";

import React, { useCallback, useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Label } from "@/components/ui/label";
import { Mail, Twitter, Facebook, Info, Send, Loader2 } from "lucide-react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

type ContentItem = {
  content: string;
  source: string;
  status?: "draft" | "approved";
  suggestions?: string;
};

const ContentCard = ({
  title,
  icon: Icon,
  content,
  status,
  suggestions,
  conversation,
}: {
  title: string;
  icon: React.ElementType;
  content: string;
  status: "draft" | "approved";
  suggestions?: string;
  conversation: ContentItem[];
}) => (
  <Card className="h-full">
    <CardHeader>
      <CardTitle className="flex items-center justify-between">
        <div className="flex items-center">
          <Icon className="mr-2 h-5 w-5" />
          {title}
        </div>
        <Badge variant={status === "approved" ? "default" : "secondary"}>
          {status}
        </Badge>
      </CardTitle>
    </CardHeader>
    <CardContent className="space-y-4">
      <ScrollArea className="h-[200px]">
        <p className="text-sm whitespace-pre-wrap">{content}</p>
      </ScrollArea>
      {suggestions && (
        <div className="bg-yellow-50 p-3 rounded-md">
          <p className="text-sm font-medium text-yellow-800">
            Editor Suggestions:
          </p>
          <p className="text-sm text-yellow-700">{suggestions}</p>
        </div>
      )}
      <Accordion type="single" collapsible className="w-full">
        <AccordionItem value="conversation">
          <AccordionTrigger>View Conversation</AccordionTrigger>
          <AccordionContent>
            <ScrollArea className="h-[200px]">
              {conversation.map((message, index) => (
                <div
                  key={index}
                  className={`flex ${
                    message.source === "User" ? "justify-end" : "justify-start"
                  } mb-4`}
                >
                  <div
                    className={`max-w-[80%] p-3 rounded-lg ${
                      message.source === "User" ? "bg-blue-100" : "bg-gray-100"
                    }`}
                  >
                    <p className="text-xs font-semibold mb-1">
                      {message.source}
                    </p>
                    <p className="text-sm">{message.content}</p>
                  </div>
                </div>
              ))}
            </ScrollArea>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </CardContent>
  </Card>
);

const ProductInfo = ({ info }: { info: string }) => (
  <Card className="h-full">
    <CardHeader>
      <CardTitle className="flex items-center">
        <Info className="mr-2 h-5 w-5" /> Product Information
      </CardTitle>
    </CardHeader>
    <CardContent>
      <ScrollArea className="h-[200px]">
        <p className="text-sm whitespace-pre-wrap">{info}</p>
      </ScrollArea>
    </CardContent>
  </Card>
);

const MarketingGenerator = () => {
  const [prompt, setPrompt] = useState("");
  const [conversation, setConversation] = useState<ContentItem[]>([]);
  const [productInfo, setProductInfo] = useState("");
  const [emailContent, setEmailContent] = useState<ContentItem>({
    content: "",
    source: "",
    status: "draft",
  });
  const [facebookContent, setFacebookContent] = useState<ContentItem>({
    content: "",
    source: "",
    status: "draft",
  });
  const [twitterContent, setTwitterContent] = useState<ContentItem>({
    content: "",
    source: "",
    status: "draft",
  });
  const [loading, setLoading] = useState(false);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (prompt.trim() && !loading) {
        setConversation([]);
        setProductInfo("");
        setEmailContent({ content: "", source: "", status: "draft" });
        setFacebookContent({ content: "", source: "", status: "draft" });
        setTwitterContent({ content: "", source: "", status: "draft" });
        setLoading(true);

        try {
          const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question: prompt }),
          });

          if (!response.ok) throw new Error("Network response was not ok");

          const reader = response.body?.getReader();
          const decoder = new TextDecoder();

          if (reader) {
            try {
              while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                console.log("Chunk received:", chunk);
                const lines = chunk.split("\n\n");

                for (const line of lines) {
                  if (line.startsWith("data: ")) {
                    const data = line.slice(6);
                    if (data === "terminated") {
                      console.log("Stream terminated by server.");
                      continue; // Continue reading the stream
                    }
                    try {
                      console.log("Received message:", data);
                      const parsedData = JSON.parse(data);
                      const output = parsedData.output;
                      const body = output.body;
                      const { content, source } = body;
                      console.log("Received message source:", source);

                      setConversation((prev) => [...prev, { content, source }]);

                      switch (source) {
                        case "ProductInformationProvider":
                          setProductInfo(content);
                          break;
                        case "EmailWriter":
                        case "Editor":
                          if (content === "APPROVE" && emailContent.content) {
                            setEmailContent((prev) => ({
                              ...prev,
                              status: "approved",
                            }));
                          } else if (
                            source === "Editor" &&
                            emailContent.content
                          ) {
                            setEmailContent((prev) => ({
                              ...prev,
                              suggestions: content,
                            }));
                          } else {
                            setEmailContent({
                              content,
                              source,
                              status: "draft",
                            });
                          }
                          break;
                        case "FacebookPostWriter":
                          if (
                            content === "APPROVE" &&
                            facebookContent.content
                          ) {
                            setFacebookContent((prev) => ({
                              ...prev,
                              status: "approved",
                            }));
                          } else if (
                            source === "Editor" &&
                            facebookContent.content
                          ) {
                            setFacebookContent((prev) => ({
                              ...prev,
                              suggestions: content,
                            }));
                          } else {
                            setFacebookContent({
                              content,
                              source,
                              status: "draft",
                            });
                          }
                          break;
                        case "TwitterPostWriter":
                          if (content === "APPROVE" && twitterContent.content) {
                            setTwitterContent((prev) => ({
                              ...prev,
                              status: "approved",
                            }));
                          } else if (
                            source === "Editor" &&
                            twitterContent.content
                          ) {
                            setTwitterContent((prev) => ({
                              ...prev,
                              suggestions: content,
                            }));
                          } else {
                            setTwitterContent({
                              content,
                              source,
                              status: "draft",
                            });
                          }
                          break;
                      }
                    } catch (error) {
                      console.error("Failed to parse message:", error);
                      console.error("Problematic data:", data);
                    }
                  }
                }
              }
            } catch (error) {
              console.error("Error reading stream:", error);
            } finally {
              reader.releaseLock();
            }
          } else {
            console.error("No reader available for the response body.");
          }
        } catch (error) {
          console.error("Error sending message:", error);
          setConversation([
            {
              content:
                "Sorry, there was an error processing your request. Please try again later.",
              source: "System",
            },
          ]);
        } finally {
          setLoading(false);
          setPrompt("");
        }
      }
    },
    [
      prompt,
      loading,
      emailContent.content,
      facebookContent.content,
      twitterContent.content,
    ]
  );

  return (
    <div className="container mx-auto p-4 space-y-8">
      <h1 className="text-3xl font-bold">
        Prudential Marketing Content Generator
      </h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <Card className="col-span-1 md:col-span-2 lg:col-span-3">
          <CardHeader>
            <CardTitle>Generate Content</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <Label htmlFor="prompt">Marketing Prompt</Label>
                <Textarea
                  id="prompt"
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="Enter your marketing prompt here..."
                  className="h-20"
                />
              </div>
              <Button type="submit" disabled={loading}>
                {loading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Generating...
                  </>
                ) : (
                  <>
                    <Send className="mr-2 h-4 w-4" />
                    Generate Content
                  </>
                )}
              </Button>
            </form>
          </CardContent>
        </Card>

        <ContentCard
          title="Email"
          icon={Mail}
          content={emailContent.content}
          status={emailContent.status}
          suggestions={emailContent.suggestions}
          conversation={conversation.filter(
            (msg) => msg.source === "EmailWriter" || msg.source === "Editor"
          )}
        />

        <ContentCard
          title="Facebook Post"
          icon={Facebook}
          content={facebookContent.content}
          status={facebookContent.status}
          suggestions={facebookContent.suggestions}
          conversation={conversation.filter(
            (msg) =>
              msg.source === "FacebookPostWriter" || msg.source === "Editor"
          )}
        />

        <ContentCard
          title="Twitter Post"
          icon={Twitter}
          content={twitterContent.content}
          status={twitterContent.status}
          suggestions={twitterContent.suggestions}
          conversation={conversation.filter(
            (msg) =>
              msg.source === "TwitterPostWriter" || msg.source === "Editor"
          )}
        />

        <ProductInfo info={productInfo} />
      </div>
    </div>
  );
};

export default MarketingGenerator;
