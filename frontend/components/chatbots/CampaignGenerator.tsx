'use client'

import { useState, useEffect, useRef } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Send, Mail, Twitter, Instagram, Facebook } from "lucide-react"

interface Message {
  content: string
  source: string
}

interface ContentCard {
  type: 'email' | 'tweet' | 'instagram' | 'facebook'
  content: string
}

const exampleMessages = [
  "Create a marketing campaign for our new life insurance product",
  "Write a social media post about our retirement planning services",
  "Draft an email newsletter about our latest investment options",
  "Compose a tweet highlighting our customer satisfaction ratings",
]

const initialCards: ContentCard[] = [
  { type: 'email', content: '' },
  { type: 'tweet', content: '' },
  { type: 'instagram', content: '' },
  { type: 'facebook', content: '' },
]

export default function SocialMediaCards() {
  const [messages, setMessages] = useState<Message[]>([])
  const [contentCards, setContentCards] = useState<ContentCard[]>(initialCards)
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const scrollAreaRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight
    }
  }, [messages])

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    if (input.trim() && !isLoading) {
      setMessages((prevMessages) => [...prevMessages, { content: input, source: 'User' }])
      setInput('')
      setIsLoading(true)

      try {
        const response = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: input }),
        })

        if (!response.ok) throw new Error('Network response was not ok')

        const reader = response.body?.getReader()
        const decoder = new TextDecoder()

        if (reader) {
          while (true) {
            const { done, value } = await reader.read()
            if (done) break

            const chunk = decoder.decode(value, { stream: true })
            const lines = chunk.split('\n\n')

            for (const line of lines) {
              if (line.startsWith('data: ')) {
                const data = line.slice(6)
                try {
                  const parsedData = JSON.parse(data)
                  const newMessage = parsedData.output.body

                  if (newMessage.source) {
                    setMessages((prevMessages) => [...prevMessages, newMessage])

                    const cardType = newMessage.source.toLowerCase().includes('email') ? 'email' :
                                     newMessage.source.toLowerCase().includes('twitter') ? 'tweet' :
                                     newMessage.source.toLowerCase().includes('instagram') ? 'instagram' :
                                     newMessage.source.toLowerCase().includes('facebook') ? 'facebook' : null

                    if (cardType) {
                      setContentCards((prevCards) => 
                        prevCards.map(card => 
                          card.type === cardType 
                            ? { ...card, content: newMessage.content.replace('APPROVE', '').trim() } 
                            : card
                        )
                      )
                    }
                  }
                } catch (error) {
                  console.error('Failed to parse message:', error)
                }
              }
            }
          }
        }
      } catch (error) {
        console.error('Error sending message:', error)
        setMessages((prevMessages) => [
          ...prevMessages,
          {
            content: 'Sorry, there was an error processing your request. Please try again later.',
            source: 'System',
          },
        ])
      } finally {
        setIsLoading(false)
      }
    }
  }

  const handleExampleClick = (example: string) => {
    setInput(example)
  }

  const renderContentCard = (card: ContentCard) => {
    switch (card.type) {
      case 'email':
        return (
          <Card className="w-full">
            <CardHeader>
              <CardTitle className="flex items-center"><Mail className="mr-2" /> Email</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <p className="font-bold">Subject: Unlock Exclusive Discounts on Pro Life Vantage!</p>
                <p>Dear Hi Matthew,</p>
                <p>{card.content || "Your email content will appear here."}</p>
                <p>Best regards,<br />[Your Insurance Company]</p>
              </div>
            </CardContent>
            <CardFooter className="justify-end space-x-2">
              <Button variant="outline">Send</Button>
              <Button variant="outline">Save Draft</Button>
            </CardFooter>
          </Card>
        )
      case 'tweet':
        return (
          <Card className="w-full">
            <CardHeader>
              <CardTitle className="flex items-center"><Twitter className="mr-2" /> Tweet</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center space-x-2 mb-2">
                <Avatar>
                  <AvatarImage src="/placeholder.svg" />
                  <AvatarFallback>P</AvatarFallback>
                </Avatar>
                <div>
                  <p className="font-bold">Prudential</p>
                  <p className="text-sm text-gray-500">@Prudential</p>
                </div>
              </div>
              <p>{card.content || "Your tweet content will appear here."}</p>
            </CardContent>
            <CardFooter className="justify-end">
              <Button variant="outline">Post</Button>
            </CardFooter>
          </Card>
        )
      case 'instagram':
        return (
          <Card className="w-full">
            <CardHeader>
              <CardTitle className="flex items-center"><Instagram className="mr-2" /> Instagram Post</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <div className="bg-gray-200 w-full h-48 flex items-center justify-center">
                  [Image Placeholder]
                </div>
                <div className="flex items-center space-x-2">
                  <Avatar>
                    <AvatarImage src="/placeholder.svg" />
                    <AvatarFallback>P</AvatarFallback>
                  </Avatar>
                  <p className="font-bold">prudential</p>
                </div>
                <p>{card.content || "Your Instagram post content will appear here."}</p>
              </div>
            </CardContent>
            <CardFooter className="justify-end">
              <Button variant="outline">Share</Button>
            </CardFooter>
          </Card>
        )
      case 'facebook':
        return (
          <Card className="w-full">
            <CardHeader>
              <CardTitle className="flex items-center"><Facebook className="mr-2" /> Facebook Post</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center space-x-2 mb-2">
                <Avatar>
                  <AvatarImage src="/placeholder.svg" />
                  <AvatarFallback>P</AvatarFallback>
                </Avatar>
                <p className="font-bold">Prudential</p>
              </div>
              <p>{card.content || "Your Facebook post content will appear here."}</p>
            </CardContent>
            <CardFooter className="justify-between">
              <Button variant="ghost">Like</Button>
              <Button variant="ghost">Comment</Button>
              <Button variant="ghost">Share</Button>
            </CardFooter>
          </Card>
        )
    }
  }

  return (
    <div className="flex flex-col h-screen max-w-6xl mx-auto p-4 space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {contentCards.map((card, index) => (
          <div key={`card-${index}`}>
            {renderContentCard(card)}
          </div>
        ))}
      </div>
      <Card>
        <CardContent className="p-4">
          <ScrollArea className="h-[200px]">
            <div className="space-y-4" ref={scrollAreaRef}>
              {messages.map((message, index) => (
                <div key={index} className="flex items-start space-x-2">
                  <Avatar>
                    <AvatarImage src={message.source === 'User' ? '/placeholder-user.jpg' : '/placeholder-bot.jpg'} />
                    <AvatarFallback>{message.source === 'User' ? 'U' : 'B'}</AvatarFallback>
                  </Avatar>
                  <div className="bg-muted p-2 rounded-lg">
                    <p className="font-semibold">{message.source}</p>
                    <p>{message.content}</p>
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>
      <div className="space-y-2">
        <div>
          <p className="text-sm font-semibold mb-2">Examples:</p>
          <div className="flex flex-wrap gap-2">
            {exampleMessages.map((example, index) => (
              <Button
                key={index}
                variant="outline"
                size="sm"
                onClick={() => handleExampleClick(example)}
              >
                {example}
              </Button>
            ))}
          </div>
        </div>
        <form onSubmit={handleSendMessage} className="flex items-center space-x-2">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your message..."
            disabled={isLoading}
            className="flex-grow"
          />
          <Button type="submit" disabled={isLoading}>
            {isLoading ? 'Sending...' : <Send className="h-4 w-4" />}
          </Button>
        </form>
      </div>
    </div>
  )
}