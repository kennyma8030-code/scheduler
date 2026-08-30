import { useState } from 'react'
import Landing from './views/Landing'
import Builder from './views/Builder'
import Results from './views/Results'
import Saved from './views/Saved'

export default function App() {
  const [view, setView] = useState('landing')
  const [termKey, setTermKey] = useState('')
  const [output, setOutput] = useState(null)     // last generate response
  const [request, setRequest] = useState(null)   // what produced it

  if (view === 'builder') {
    return (
      <Builder
        termKey={termKey}
        onBack={() => setView('landing')}
        onResults={(out, req) => { setOutput(out); setRequest(req); setView('results') }}
      />
    )
  }
  if (view === 'results' && output) {
    return (
      <Results
        output={output}
        request={request}
        onBack={() => setView('builder')}
        onResults={(out, req) => { setOutput(out); setRequest(req) }}
      />
    )
  }
  if (view === 'saved') {
    return <Saved onBack={() => setView('landing')} />
  }
  return (
    <Landing
      onStart={(next, key) => {
        if (key) setTermKey(key)
        setView(next)
      }}
    />
  )
}
