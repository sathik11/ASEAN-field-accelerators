import React, { useState } from "react";
import { CheckCircle2, Circle, Download, Settings, Zap } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

interface InitializationStep {
  type: "initialization";
  title: string;
  content: string;
  files?: { name: string; path: string }[];
}

interface InitializationStepperProps {
  steps: InitializationStep[];
  currentStep: number;
}

export default function InitializationStepper({
  steps,
  currentStep,
}: InitializationStepperProps) {
  const [expandedStep, setExpandedStep] = useState<number | null>(null);

  const getStepIcon = (index: number) => {
    if (index < currentStep) return <CheckCircle2 className="text-green-500" />;
    if (index === currentStep) return <Circle className="text-blue-500" />;
    return <Circle className="text-gray-300" />;
  };

  const getStepContentIcon = (index: number) => {
    switch (index) {
      case 0:
        return <Zap className="text-yellow-500" />;
      case 1:
        return <Download className="text-blue-500" />;
      case 2:
        return <Settings className="text-purple-500" />;
      case 3:
        return <CheckCircle2 className="text-green-500" />;
      default:
        return <Circle />;
    }
  };

  return (
    <div className="bg-muted rounded-lg p-4 mb-4">
      <h3 className="text-lg font-semibold mb-4">Initialization Progress</h3>
      <div className="space-y-4">
        {steps.map((step, index) => (
          <div key={index} className="flex items-start">
            <div className="flex-shrink-0 mr-4 mt-1">{getStepIcon(index)}</div>
            <div className="flex-grow">
              <Accordion type="single" collapsible>
                <AccordionItem value={`step-${index}`}>
                  <AccordionTrigger
                    onClick={() =>
                      setExpandedStep(expandedStep === index ? null : index)
                    }
                    className={`text-left ${
                      index === currentStep ? "font-semibold" : ""
                    }`}
                  >
                    {step.title}
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="pl-4 border-l-2 border-muted-foreground/20">
                      <div className="flex items-center mb-2">
                        {getStepContentIcon(index)}
                        <span className="ml-2 font-medium">Details</span>
                      </div>
                      <p className="text-sm mb-2">{step.content}</p>
                      {step.files && step.files.length > 0 && (
                        <div>
                          <h4 className="font-medium mt-2 mb-1">Files:</h4>
                          <ScrollArea className="h-[100px]">
                            <ul className="list-disc pl-5 space-y-1">
                              {step.files.map((file, fileIndex) => (
                                <li key={fileIndex} className="text-sm">
                                  <span>{file.name}</span>
                                  <span className="text-muted-foreground ml-2">
                                    ({file.path})
                                  </span>
                                </li>
                              ))}
                            </ul>
                          </ScrollArea>
                        </div>
                      )}
                    </div>
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
