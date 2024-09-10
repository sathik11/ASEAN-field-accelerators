"use client";

import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

export default function CampaignGenerator() {
  const [product, setProduct] = useState("");
  const [targetAudience, setTargetAudience] = useState("");
  const [campaignGoal, setCampaignGoal] = useState("");
  const [generatedCampaign, setGeneratedCampaign] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    // Here you would typically make an API call to generate the campaign
    // For now, we'll just simulate a delay and set some dummy text
    setTimeout(() => {
      setGeneratedCampaign(
        `Campaign for ${product} targeting ${targetAudience} with the goal of ${campaignGoal}.`
      );
      setIsLoading(false);
    }, 2000);
  };

  return (
    <div className="space-y-4">
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          placeholder="Product or Service"
          value={product}
          onChange={(e) => setProduct(e.target.value)}
          required
        />
        <Input
          placeholder="Target Audience"
          value={targetAudience}
          onChange={(e) => setTargetAudience(e.target.value)}
          required
        />
        <Textarea
          placeholder="Campaign Goal"
          value={campaignGoal}
          onChange={(e) => setCampaignGoal(e.target.value)}
          required
        />
        <Button type="submit" disabled={isLoading}>
          {isLoading ? "Generating..." : "Generate Campaign"}
        </Button>
      </form>
      {generatedCampaign && (
        <div className="mt-4 p-4 bg-muted rounded-lg">
          <h3 className="text-lg font-semibold mb-2">Generated Campaign:</h3>
          <p>{generatedCampaign}</p>
        </div>
      )}
    </div>
  );
}
