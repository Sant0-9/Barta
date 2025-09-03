'use client'

import React, { useState, useEffect, useRef } from 'react'

interface Message {
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
}

interface Source {
  index: number
  title: string
  url: string
  source_domain: string
  published_at?: string
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  
  // Load conversation ID from localStorage on mount
  useEffect(() => {
    const savedConversationId = localStorage.getItem('barta-conversation-id')
    if (savedConversationId) {
      setConversationId(savedConversationId)
    }
  }, [])
  
  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return
    
    console.log('Submitting message:', input.trim(), 'isLoading:', isLoading)
    
    const userMessage = input.trim()
    setInput('')
    setIsLoading(true)
    
    // Add user message to chat
    setMessages(prev => [...prev, { role: 'user', content: userMessage }])
    
    // Add placeholder for assistant message
    setMessages(prev => [...prev, { role: 'assistant', content: '' }])
    const assistantMessageIndex = messages.length + 1
    
    try {
      // Send request to chat API
      const response = await fetch('/api/ask', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: userMessage,
          conversation_id: conversationId
        })
      })
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      
      // Read SSE stream
      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('No response stream')
      }
      
      // Use EventSource-like parsing
      const decoder = new TextDecoder()
      let buffer = ''
      
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || '' // Keep incomplete line
        
        let i = 0
        while (i < lines.length) {
          const line = lines[i]
          if (line.startsWith('event: ') && i + 1 < lines.length) {
            const event = line.substring(7).trim()
            const dataLine = lines[i + 1]
            
            if (dataLine.startsWith('data: ')) {
              const dataStr = dataLine.substring(6).trim()
              
              try {
                const data = JSON.parse(dataStr)
                
                if (event === 'delta' && data.token) {
                  setMessages(prev => {
                    return prev.map((message, index) => {
                      if (index === assistantMessageIndex && message.role === 'assistant') {
                        return {
                          ...message,
                          content: message.content + data.token
                        }
                      }
                      return message
                    })
                  })
                } else if (event === 'done') {
                  if (data.conversation_id && !conversationId) {
                    setConversationId(data.conversation_id)
                    localStorage.setItem('barta-conversation-id', data.conversation_id)
                  }
                  
                  if (data.sources && data.sources.length > 0) {
                    setMessages(prev => {
                      return prev.map((message, index) => {
                        if (index === assistantMessageIndex && message.role === 'assistant') {
                          return {
                            ...message,
                            sources: data.sources
                          }
                        }
                        return message
                      })
                    })
                  }
                } else if (event === 'error') {
                  console.error('Stream error:', data.message)
                  setMessages(prev => {
                    return prev.map((message, index) => {
                      if (index === assistantMessageIndex && message.role === 'assistant') {
                        return {
                          ...message,
                          content: 'Sorry, I encountered an error processing your request.'
                        }
                      }
                      return message
                    })
                  })
                  return
                }
              } catch (parseError) {
                console.error('Failed to parse SSE:', parseError)
              }
              
              i += 2 // Skip both event and data lines
            } else {
              i++
            }
          } else {
            i++
          }
        }
      }
    } catch (error) {
      console.error('Chat error:', error)
      setMessages(prev => {
        return prev.map((message, index) => {
          if (index === assistantMessageIndex && message.role === 'assistant') {
            return {
              ...message,
              content: 'Sorry, I encountered a connection error. Please try again.'
            }
          }
          return message
        })
      })
    } finally {
      console.log('Setting isLoading to false')
      setIsLoading(false)
    }
  }
  
  const formatMessageContent = (content: string, sources?: Source[]) => {
    if (!sources || sources.length === 0) {
      return content
    }
    
    // Replace citation markers with clickable links
    let formattedContent = content
    sources.forEach((source) => {
      const citation = `[${source.index}]`
      const replacement = `<a href="#source-${source.index}" class="text-blue-400 hover:text-blue-300 no-underline font-medium">${citation}</a>`
      formattedContent = formattedContent.replace(new RegExp(citation.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'), replacement)
    })
    
    return formattedContent
  }
  
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 space-y-4">
      <h2 className="text-xl font-semibold text-slate-200">Chat with Barta</h2>
      
      {/* Messages Container */}
      <div className="bg-slate-800 border border-slate-700 rounded p-4 h-96 overflow-y-auto space-y-4">
        {messages.length === 0 && (
          <div className="h-full flex items-center justify-center">
            <p className="text-slate-400 text-center">
              Ask me about recent news and I'll provide analysis with sources.
            </p>
          </div>
        )}
        
        {messages.map((message, index) => (
          <div key={index} className={`space-y-2 ${message.role === 'user' ? 'ml-8' : 'mr-8'}`}>
            {/* Message Bubble */}
            <div className={`p-3 rounded-lg ${
              message.role === 'user' 
                ? 'bg-blue-600 text-white ml-auto max-w-[80%]' 
                : 'bg-slate-700 text-slate-100 max-w-[90%]'
            }`}>
              {message.role === 'assistant' ? (
                <div 
                  className="prose prose-slate prose-invert prose-sm max-w-none whitespace-pre-wrap"
                  dangerouslySetInnerHTML={{ 
                    __html: formatMessageContent(message.content, message.sources) 
                  }}
                />
              ) : (
                <p className="whitespace-pre-wrap">{message.content}</p>
              )}
            </div>
            
            {/* Sources */}
            {message.sources && message.sources.length > 0 && (
              <div className="bg-slate-750 border border-slate-600 rounded p-3 max-w-[90%]">
                <h4 className="text-sm font-medium text-slate-300 mb-2">Sources:</h4>
                <ul className="space-y-1 text-sm">
                  {message.sources.map((source) => (
                    <li key={source.index} id={`source-${source.index}`} className="text-slate-400">
                      <span className="text-blue-400 font-medium">[{source.index}]</span>{' '}
                      <a 
                        href={source.url} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="text-slate-300 hover:text-white underline"
                      >
                        {source.title}
                      </a>
                      <span className="text-slate-500"> ({source.source_domain})</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
        
        {/* Loading indicator */}
        {isLoading && messages[messages.length - 1]?.role === 'assistant' && !messages[messages.length - 1]?.content && (
          <div className="flex items-center space-x-2 text-slate-400">
            <div className="animate-spin h-4 w-4 border-2 border-slate-400 border-t-transparent rounded-full"></div>
            <span>Thinking...</span>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>
      
      {/* Input Form */}
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about recent news..."
          className="flex-1 bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
          disabled={isLoading}
          maxLength={2000}
        />
        <button
          type="submit"
          className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 rounded text-white transition-colors"
          disabled={isLoading || !input.trim()}
        >
          {isLoading ? (
            <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full"></div>
          ) : (
            'Send'
          )}
        </button>
      </form>
      
      {/* Helper Text */}
      <p className="text-xs text-slate-500 text-center">
        {conversationId ? `Conversation: ${conversationId.slice(0, 8)}...` : 'New conversation will be started'}
      </p>
    </div>
  )
}