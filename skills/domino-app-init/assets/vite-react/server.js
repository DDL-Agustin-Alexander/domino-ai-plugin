// Serves the Vite build and keeps the model endpoint token on the server.
// Requires: "type": "module" in package.json (the Vite scaffold sets it) and `npm install express`.
import express from 'express'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const dist = path.join(path.dirname(fileURLToPath(import.meta.url)), 'dist')
const app = express()
app.use(express.json())

// POST /api/predict -> Domino endpoint. The frontend calls this route relatively
// (new URL('api/', document.baseURI)), so it works under the Domino proxy prefix.
// Synchronous Domino endpoints use HTTP Basic with the Model Access Token as user and password;
// asynchronous endpoints use "Authorization: Bearer <token>" instead.
app.post('/api/predict', async (req, res) => {
  const url = process.env.MODEL_API_URL
  const token = process.env.MODEL_API_TOKEN
  if (!url || !token) {
    return res.status(500).json({ error: 'MODEL_API_URL or MODEL_API_TOKEN is not set in the project environment variables' })
  }
  const basic = Buffer.from(token + ':' + token).toString('base64')
  try {
    const upstream = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: 'Basic ' + basic },
      body: JSON.stringify({ data: req.body }),
    })
    res.status(upstream.status).type('application/json').send(await upstream.text())
  } catch (err) {
    console.error('model endpoint call failed:', err)
    res.status(502).json({ error: 'model endpoint call failed' })
  }
})

// Static files from the Vite build, then an SPA fallback (harmless with HashRouter).
app.use(express.static(dist))
app.use((req, res) => res.sendFile(path.join(dist, 'index.html')))

// Domino Apps must listen on 0.0.0.0:8888.
app.listen(8888, '0.0.0.0', () => console.log('listening on 0.0.0.0:8888'))
