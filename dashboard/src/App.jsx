import React from "react";
import { BrowserRouter, Link, Route, Routes, useLocation } from "react-router-dom";

import Conversation from "./pages/Conversation.jsx";
import NPCDetail from "./pages/NPCDetail.jsx";
import Overview from "./pages/Overview.jsx";
import Perception from "./pages/Perception.jsx";
import Simulation from "./pages/Simulation.jsx";

function NavLink({ to, children }) {
  const location = useLocation();
  const active = location.pathname === to || (to !== "/" && location.pathname.startsWith(to));
  return (
    <Link
      to={to}
      className={`text-sm font-medium transition ${active ? "text-teal-700" : "text-stone-500 hover:text-stone-900"}`}
    >
      {children}
    </Link>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen">
        <header className="border-b border-stone-200 bg-white">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
            <Link to="/" className="text-lg font-semibold tracking-normal text-stone-950">
              SentientNPC
            </Link>
            <nav className="flex items-center gap-5">
              <NavLink to="/">Overview</NavLink>
              <NavLink to="/simulation">Simulation</NavLink>
              <NavLink to="/perception">Perception</NavLink>
              <NavLink to="/conversation">Conversation</NavLink>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-6">
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/npc/:id" element={<NPCDetail />} />
            <Route path="/simulation" element={<Simulation />} />
            <Route path="/perception" element={<Perception />} />
            <Route path="/conversation" element={<Conversation />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
