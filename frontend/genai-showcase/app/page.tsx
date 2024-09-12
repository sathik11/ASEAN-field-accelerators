"use client";

import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import WebResearcher from "@/components/chatbots/WebResearcher";
import DocumentProcessor from "@/components/chatbots/DocumentProcessor";

export default function Home() {
  const [activeTab, setActiveTab] = useState("web-researcher");

  return (
    <main className="container mx-auto p-4">
      <h1 className="text-3xl font-bold mb-8 text-center">
        GenAI Chatbot Showcase
      </h1>
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="web-researcher">Web Researcher</TabsTrigger>
          <TabsTrigger value="document-processor">
            Document Processor
          </TabsTrigger>
        </TabsList>
        <TabsContent value="web-researcher" className="mt-6">
          <WebResearcher />
        </TabsContent>

        <TabsContent value="document-processor" className="mt-6">
          <DocumentProcessor />
        </TabsContent>
      </Tabs>
    </main>
  );
}

// Add generateStaticParams function
// export async function generateStaticParams() {
//   return [{ tab: "web-researcher" }, { tab: "document-processor" }];
// }
