import React, { useState, useEffect } from 'react'
import ReactDOM from 'react-dom/client'
import axios from 'axios'
import './index.css'

function App() {
  const [health, setHealth] = useState('Vérification...')
  const [data, setData] = useState(null)

  // REMPLACER useEffect (ligne 20-27)
useEffect(() => {
  // Test direct backend (sans proxy)
  fetch('https://apexai-backend-v2.onrender.com/health')
    .then(res => res.ok ? setHealth('✅ Backend OK!') : setHealth('❌ 404'))
    .catch(() => setHealth('❌ Erreur réseau'));
}, [])

// REMPLACER testAPI (ligne 29-36)
const testAPI = async () => {
  try {
    const res = await fetch('https://apexai-backend-v2.onrender.com/');
    const data = await res.json();
    setData(data);
  } catch (error) {
    setData('Erreur: ' + error.message);
  }
};

