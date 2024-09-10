"use client";

import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import WebResearcher from "@/components/WebResearcher";
import CampaignGenerator from "@/components/CampaignGenerator";
import Other from "@/components/Other";

export default function GenAIShowcase() {
  const [activeTab, setActiveTab] = useState("web-researcher");

  const chatbots = [
    {
      id: "web-researcher",
      name: "Web Researcher",
      description: "Personal Research Assistant",
      component: <WebResearcher />,
    },
    {
      id: "campaign-generator",
      name: "Campaign Generator",
      description: "AI Marketing Assistant",
      component: <CampaignGenerator />,
    },
    {
      id: "other",
      name: "Other",
      description: "Language Model",
      component: <Other />,
    },
  ];

  return (
    <div className="container mx-auto p-4">
      <h1 className="text-3xl font-bold mb-6">GenAI Chatbot Showcase</h1>
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-3">
          {chatbots.map((bot) => (
            <TabsTrigger key={bot.id} value={bot.id}>
              {bot.name}
            </TabsTrigger>
          ))}
        </TabsList>
        {chatbots.map((bot) => (
          <TabsContent key={bot.id} value={bot.id}>
            <Card>
              <CardHeader>
                <CardTitle>{bot.name}</CardTitle>
                <CardDescription>{bot.description}</CardDescription>
              </CardHeader>
              <CardContent>{bot.component}</CardContent>
            </Card>
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
