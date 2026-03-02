import { useState, useRef, useEffect } from 'react'
import axios from 'axios'
import './App.css'

const API_BASE_URL = 'http://127.0.0.1:5000/'
const API_CHAT = '/api/chat'
const API_LEGACY = '/get'

function formatTime(date = new Date()) {
  return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true })
}

const LANG_LABELS = { en: 'English', es: 'Spanish', pt: 'Portuguese' }

function App() {
  const [messages, setMessages] = useState([
    {
      id: 1,
      text: "Hello! I'm the Braelo assistant. Ask me about living in the USA or finding local services (e.g. lawyer in Florida, tax preparer in Texas). I support English, Spanish, and Portuguese.",
      sender: 'bot',
      time: formatTime(),
      businesses: [],
      detectedLanguage: null,
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef(null)
  const [sessionId] = useState(() => `web-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`)

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
      businesses: [],
      detectedLanguage: null,
    }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const { data } = await axios.post(
        `${API_BASE_URL}${API_CHAT}`,
        { message: text, session_id: sessionId },
        { headers: { 'Content-Type': 'application/json' }, timeout: 60000 }
      )
      const botMsg = {
        id: Date.now() + 1,
        text: typeof data === 'string' ? data : (data?.response ?? data?.error ?? 'No response'),
        sender: 'bot',
        time: formatTime(),
        businesses: Array.isArray(data?.businesses) ? data.businesses : [],
        detectedLanguage: data?.detected_language || null,
        questionAnalysis: data?.question_analysis || null,
      }
      setMessages((prev) => [...prev, botMsg])
    } catch (err) {
      const fallback = err.response?.status === 404 || err.response?.data?.error
        ? null
        : await (async () => {
            try {
              const r = await axios.post(
                `${API_BASE_URL}${API_LEGACY}`,
                new URLSearchParams({ msg: text }),
                { headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, timeout: 15000 }
              )
              return typeof r.data === 'string' ? r.data : r.data?.response
            } catch {
              return null
            }
          })()
      const botMsg = {
        id: Date.now() + 1,
        text: fallback || 'Sorry, something went wrong. Make sure the backend is running on http://localhost:5000 and OPENAI_API_KEY is set for the full assistant.',
        sender: 'bot',
        time: formatTime(),
        businesses: [],
        detectedLanguage: null,
      }
      setMessages((prev) => [...prev, botMsg])
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
      <div className="w-full max-w-md md:max-w-lg lg:max-w-xl min-h-screen md:rounded-2xl md:shadow-lg md:my-8 flex flex-col bg-white overflow-hidden">
        <header className="flex-shrink-0 flex items-center gap-3 px-4 py-3 border-b border-gray-100 bg-white">
          <div className="w-10 h-10 rounded-full bg-indigo-600 flex items-center justify-center flex-shrink-0">
            <span className="text-white text-xs font-semibold">B</span>
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="font-semibold text-gray-900 truncate">Braelo Assistant</h1>
            <p className="text-sm text-gray-500">English · Español · Português</p>
          </div>
        </header>

        <div className="flex-shrink-0 flex items-center gap-3 px-4 py-2">
          <span className="flex-1 h-px bg-gray-200" />
          <span className="text-sm text-gray-500">Today</span>
          <span className="flex-1 h-px bg-gray-200" />
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-2 pb-20 space-y-4">
          {messages.map((msg) =>
            msg.sender === 'bot' ? (
              <div key={msg.id} className="flex gap-3 justify-start">
                <div className="w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <span className="text-white text-xs font-semibold">B</span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline gap-2 flex-wrap">
                    <span className="text-sm font-medium text-gray-900">Braelo</span>
                    {/* {msg.detectedLanguage && (
                      <span className="text-xs text-gray-500">
                        ({LANG_LABELS[msg.detectedLanguage] || msg.detectedLanguage})
                      </span>
                    )} */}
                    <span className="text-xs text-gray-400">{msg.time}</span>
                  </div>
                  <div className="mt-0.5 rounded-xl rounded-tl-sm bg-gray-100 px-4 py-2.5 text-gray-800 text-[15px] whitespace-pre-wrap">
                    {msg.text}
                  </div>
                  {msg.questionAnalysis && (
                    <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-gray-500">
                      <span>Intent: {msg.questionAnalysis.intent || '—'}</span>
                      {msg.questionAnalysis.category && <span>Category: {msg.questionAnalysis.category}</span>}
                      {msg.questionAnalysis.state && <span>State: {msg.questionAnalysis.state}</span>}
                      {msg.questionAnalysis.detected_language && (
                        <span>Language: {LANG_LABELS[msg.questionAnalysis.detected_language] || msg.questionAnalysis.detected_language}</span>
                      )}
                    </div>
                  )}
                  {msg.businesses && msg.businesses.length > 0 && (
                    <div className="mt-2 space-y-2">
                      <p className="text-xs font-medium text-gray-600">Local businesses</p>
                      {msg.businesses.map((b) => (
                        <a
                          key={b.id}
                          href={b.contact_info?.startsWith('http') ? b.contact_info : `tel:${b.contact_info || ''}`}
                          target={b.contact_info?.startsWith('http') ? '_blank' : undefined}
                          rel="noopener noreferrer"
                          className="block rounded-lg border border-gray-200 bg-white p-3 text-left hover:border-indigo-300 hover:bg-indigo-50/50 transition"
                        >
                          <span className="font-medium text-gray-900">{b.name}</span>
                          {(b.category || b.subcategory) && (
                            <span className="text-gray-500 text-sm ml-1">
                              {[b.category, b.subcategory].filter(Boolean).join(' · ')}
                            </span>
                          )}
                          {(b.city || b.state) && (
                            <p className="text-xs text-gray-500 mt-0.5">{[b.city, b.state].filter(Boolean).join(', ')}</p>
                          )}
                          {b.contact_info && (
                            <p className="text-xs text-indigo-600 mt-1 truncate">{b.contact_info}</p>
                          )}
                        </a>
                      ))}
                    </div>
                  )}
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
                <span className="text-white text-xs font-semibold">B</span>
              </div>
              <div className="rounded-xl rounded-tl-sm bg-gray-100 px-4 py-2.5 text-gray-500 text-sm">
                Typing...
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="flex-shrink-0 flex items-center gap-2 px-4 py-3 bg-white border-t border-gray-100">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask in English, Spanish, or Portuguese..."
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
