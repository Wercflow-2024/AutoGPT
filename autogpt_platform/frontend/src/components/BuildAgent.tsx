"use client";

import { useState } from 'react'

export default function BuildAgent() {
  const [url, setUrl] = useState('')
  const [instructions, setInstructions] = useState('Extract project title, credits, video link')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const runScraper = async () => {
    setLoading(true)
    setResult(null)
    setError(null)
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/scraper`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, instructions })
      })

      if (!response.ok) throw new Error(`Status ${response.status}`)
      const data = await response.json()
      setResult(data)
    } catch (err: any) {
      setError(err?.message || 'Unexpected error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-4">
      <h1 className="text-2xl font-bold">Build a Scraper Agent</h1>

      <div>
        <label className="block mb-1 font-medium">Target URL</label>
        <input
          type="text"
          className="w-full border rounded p-2"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://example.com/page"
        />
      </div>

      <div>
        <label className="block mb-1 font-medium">Instructions</label>
        <textarea
          className="w-full border rounded p-2"
          value={instructions}
          onChange={(e) => setInstructions(e.target.value)}
        />
      </div>

      <button
        onClick={runScraper}
        disabled={loading || !url}
        className="bg-black text-white px-4 py-2 rounded hover:bg-gray-800 disabled:opacity-50"
      >
        {loading ? 'Running...' : 'Run Scraper'}
      </button>

      {error && <p className="text-red-500">Error: {error}</p>}

      {result && (
        <div className="mt-6">
          <h2 className="text-lg font-semibold mb-2">Scraped Result:</h2>
          <pre className="bg-gray-100 p-4 rounded text-sm overflow-auto">
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}
