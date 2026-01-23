import React, { useState, useEffect } from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'

function App() {
  const [health, setHealth] = useState('⏳ Test en cours...')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetch('https://apexai-backend-v2.onrender.com/api/health')
      .then(res => {
        if (res.ok) return res.json()
        throw new Error(`HTTP ${res.status}`)
      })
      .then(json => setHealth('✅ Backend OK!'))
      .catch(err => setHealth(`❌ ${err.message}`))
  }, [])

  const testAPI = async () => {
    setLoading(true)
    try {
      const res = await fetch('https://apexai-backend-v2.onrender.com/api')
      const json = await res.json()
      setData(json)
    } catch (error) {
      setData({ error: error.message })
    }
    setLoading(false)
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-5xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent mb-8">
          🏎️ ApexAI Race Coach
        </h1>
        
        <div className="bg-white p-8 rounded-2xl shadow-xl mb-8 border-4 border-green-200">
          <h2 className="text-2xl font-semibold mb-4 text-gray-800">Statut Système</h2>
          <div className="space-y-3">
            <p className="text-2xl font-bold p-4 bg-green-50 rounded-xl">
              Backend: {health}
            </p>
            <p className="text-sm text-gray-500">
              API: <a href="https://apexai-backend-v2.onrender.com/docs" 
                className="text-blue-600 hover:underline font-mono">
                apexai-backend-v2.onrender.com
              </a>
            </p>
          </div>
        </div>

        <button
          onClick={testAPI}
          disabled={loading}
          className="bg-blue-600 text-white px-10 py-6 rounded-2xl text-xl font-bold hover:bg-blue-700 transition-all shadow-xl transform hover:-translate-y-1 disabled:opacity-50"
        >
          {loading ? '⏳ Test...' : '🚀 Test API Backend'}
        </button>

        {data && (
          <div className="mt-8">
            <h3 className="text-xl font-semibold mb-4">Réponse Backend:</h3>
            <pre className="p-6 bg-gray-900 text-green-400 rounded-2xl font-mono text-sm overflow-auto max-h-96">
              {JSON.stringify(data, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  )
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
