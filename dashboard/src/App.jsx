import { BrowserRouter, Link, Route, Routes } from "react-router-dom";

import NPCDetail from "./pages/NPCDetail.jsx";
import Overview from "./pages/Overview.jsx";

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen">
        <header className="border-b border-stone-200 bg-white">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
            <Link to="/" className="text-lg font-semibold tracking-normal text-stone-950">
              SentientNPC
            </Link>
            <span className="text-sm text-stone-500">Live NPC State</span>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-6">
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/npc/:id" element={<NPCDetail />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
