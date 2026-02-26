import { useState, useRef, useEffect } from 'react'
import axios from 'axios'
import './App.css'

const API_BASE_URL = 'http://localhost:5000'
const API_ENDPOINT = '/get'

function formatTime(date = new Date()) {
  return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true })
}

function App() {
  const [messages, setMessages] = useState([
    {
      id: 1,
      text: "Hello, how can I help you today?",
      sender: 'bot',
      time: '10:00 AM',
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const sendMessage = async () => {
    const text = input.trim()
    if (!text || loading) return

    const userMsg = {
      id: Date.now(),
      text,
      sender: 'user',
      time: formatTime(),
    }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const { data } = await axios.post(
        `${API_BASE_URL}${API_ENDPOINT}`,
        new URLSearchParams({ msg: text }),
        { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
      )
      const botMsg = {
        id: Date.now() + 1,
        text: typeof data === 'string' ? data : data?.response || JSON.stringify(data),
        sender: 'bot',
        time: formatTime(),
      }
      setMessages((prev) => [...prev, botMsg])
    } catch (err) {
      const errorMsg = {
        id: Date.now() + 1,
        text: 'Sorry, something went wrong. Make sure the backend is running on http://localhost:5000',
        sender: 'bot',
        time: formatTime(),
      }
      setMessages((prev) => [...prev, errorMsg])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="min-h-screen bg-white flex flex-col items-center">
      {/* Chat container - web view: max-width card */}
      <div className="w-full max-w-md md:max-w-lg lg:max-w-xl min-h-screen md:rounded-2xl md:shadow-lg md:my-8 flex flex-col bg-white overflow-hidden">
        {/* Header */}
        <header className="flex-shrink-0 flex items-center gap-3 px-4 py-3 border-b border-gray-100 bg-white">
          <button
            type="button"
            className="p-2 -ml-1 rounded-full hover:bg-gray-100 text-gray-700"
            aria-label="Back"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div className="w-10 h-10 rounded-full bg-indigo-600 flex items-center justify-center flex-shrink-0">
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="font-semibold text-gray-900 truncate">Chat Bot</h1>
            <p className="text-sm text-gray-500">Online</p>
          </div>
        </header>

        {/* Date separator */}
        <div className="flex-shrink-0 flex items-center gap-3 px-4 py-2">
          <span className="flex-1 h-px bg-gray-200" />
          <span className="text-sm text-gray-500">Today</span>
          <span className="flex-1 h-px bg-gray-200" />
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-2 space-y-4">
          {messages.map((msg) =>
            msg.sender === 'bot' ? (
              <div key={msg.id} className="flex gap-3 justify-start">
                <div className="w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <span className="text-white text-xs font-semibold">CB</span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline gap-2">
                    <span className="text-sm font-medium text-gray-900">CB assistant</span>
                    <span className="text-xs text-gray-400">{msg.time}</span>
                  </div>
                  <div className="mt-0.5 rounded-xl rounded-tl-sm bg-gray-100 px-4 py-2.5 text-gray-800 text-[15px]">
                    {msg.text}
                  </div>
                </div>
              </div>
            ) : (
              <div key={msg.id} className="flex justify-end">
                <div className="max-w-[85%]">
                  <div className="flex justify-end">
                    <span className="text-xs text-gray-400">{msg.time}</span>
                  </div>
                  <div className="mt-0.5 rounded-xl rounded-br-sm bg-indigo-600 px-4 py-2.5 text-white text-[15px]">
                    {msg.text}
                  </div>
                </div>
              </div>
            )
          )}
          {loading && (
            <div className="flex gap-3 justify-start">
              <div className="w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-white text-xs font-semibold">CB</span>
              </div>
              <div className="rounded-xl rounded-tl-sm bg-gray-100 px-4 py-2.5 text-gray-500 text-sm">
                Typing...
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input bar */}
        <div className="flex-shrink-0 flex items-center gap-2 px-4 py-3 bg-white border-t border-gray-100">
          <button
            type="button"
            className="w-10 h-10 rounded-full border border-gray-200 flex items-center justify-center text-gray-600 hover:bg-gray-50 flex-shrink-0"
            aria-label="Attach"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 5v14M5 12h14" />
            </svg>
          </button>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Hello,...."
            className="flex-1 min-w-0 rounded-full border border-gray-200 px-4 py-2.5 text-[15px] placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
            disabled={loading}
          />
          <button
            type="button"
            onClick={sendMessage}
            disabled={!input.trim() || loading}
            className="w-10 h-10 rounded-full bg-indigo-600 flex items-center justify-center text-white flex-shrink-0 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
            aria-label="Send"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}

export default App
