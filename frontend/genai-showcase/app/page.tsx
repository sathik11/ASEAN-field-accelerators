// page.tsx
"use client";

import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import WebResearcher from "@/components/chatbots/WebResearcher";
import DocumentProcessor from "@/components/chatbots/DocumentProcessor";
import CampaignGenerator from "@/components/chatbots/CampaignGenerator";
export default function Home() {
  const [activeTab, setActiveTab] = useState("web-researcher");

  return (
    <div className="space-y-8">
      <section className="text-center"></section>
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="flex justify-center space-x-4">
          <TabsTrigger value="web-researcher">Web Researcher</TabsTrigger>
          <TabsTrigger value="document-processor">
            Document Processor
          </TabsTrigger>
          <TabsTrigger value="campaign-generator">
            Campaign Generator
          </TabsTrigger>
        </TabsList>
        <TabsContent value="web-researcher" className="mt-6">
          <WebResearcher />
        </TabsContent>
        <TabsContent value="document-processor" className="mt-6">
          <DocumentProcessor />
        </TabsContent>
        <TabsContent value="campaign-generator" className="mt-6">
          <CampaignGenerator />
        </TabsContent>
      </Tabs>
    </div>
  );
}
