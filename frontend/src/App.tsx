import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Analysis } from './pages/Analysis'
import { Home } from './pages/Home'
import { Setup } from './pages/Setup'
import { Upload } from './pages/Upload'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="new" element={<Setup />} />
          <Route path="sessions/:sessionId/upload" element={<Upload />} />
          <Route path="sessions/:sessionId/analysis" element={<Analysis />} />
          <Route path="*" element={<p className="text-slate-500">Page not found.</p>} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
