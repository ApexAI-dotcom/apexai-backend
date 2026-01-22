import React, { useState, useEffect } from 'react'
import ReactDOM from 'react-dom/client'
import axios from 'axios'
import './index.css'

function App() {
  const [health, setHealth] = useState('Vérification...')
  const [data, setData] = useState(null)

  useEffect(() => {
    // Test backend auto
    axios.get('/api/health').then(res => {
      setHealth('✅ Backend OK!')
    }).catch(err => {
      setHealth('❌ Backend erreur')
    })
  }, [])

  const testAPI = async () => {
    try {
      const res = await axios.get('/api/')  // Remplacez par votre endpoint
      setData(res.data)
    } catch (error) {
      console.error(error)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-4xl font-bold text-gray-900 mb-8">
          🚀 ApexAI WebApp
        </h1>
        
        <div className="bg-white p-8 rounded-2xl shadow-xl mb-8">
          <h2 className="text-2xl font-semibold mb-4">Statut Backend</h2>
          <p className="text-xl">{health}</p>
        </div>

        <button
          onClick={testAPI}
          className="bg-blue-600 text-white px-8 py-4 rounded-xl text-lg font-semibold hover:bg-blue-700 transition-all shadow-lg"
        >
          Test API Backend
        </button>

        {data && (
          <pre className="mt-8 p-6 bg-gray-100 rounded-xl font-mono">
            {JSON.stringify(data, null, 2)}
          </pre>
        )}
      </div>
    </div>
  )
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
