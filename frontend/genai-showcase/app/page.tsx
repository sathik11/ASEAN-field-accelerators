import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import ChatInterface from "@/components/ChatInterface";

export default function GenAIShowcase() {
  const chatbots = [
    {
      id: "web-researcher",
      name: "Web Researcher",
      description: "Personal Research Assistant",
    },
    {
      id: "campaing-generator",
      name: "Campaign Generator",
      description: "AI assistant",
    },
    {
      id: "other",
      name: "Other",
      description: "Language Model",
    },
  ];

  return (
    <div className="container mx-auto p-4">
      <h1 className="text-3xl font-bold mb-6">GenAI Chatbot Showcase</h1>
      <Tabs defaultValue="gpt-3.5">
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
              <CardContent>
                <ChatInterface botId={bot.id} />
              </CardContent>
            </Card>
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
