import { Routes, Route, NavLink, Navigate } from 'react-router-dom'
import Home from './pages/Home.jsx'
import MapPage from './pages/MapPage.jsx'
import Loot from './pages/Loot.jsx'
import Crafting from './pages/Crafting.jsx'
import Builder from './pages/Builder.jsx'
import BuilderV2 from './pages/BuilderV2.jsx'
import TechTree from './pages/TechTree.jsx'
import Contracts from './pages/Contracts.jsx'
import Gallery from './pages/Gallery.jsx'
import Moderate from './pages/Moderate.jsx'

export default function App() {
  return (
    <div className="shell">
      <header className="topbar">
        <NavLink to="/" className="brand">
          <div>
            <div className="brand-mark">SAND</div>
            <div className="brand-sub">Expedition Kit</div>
          </div>
        </NavLink>
        <nav className="nav">
          <NavLink to="/map">Ops Board</NavLink>
          <NavLink to="/loot">Loot</NavLink>
          <NavLink to="/crafting">Crafting</NavLink>
          <NavLink to="/builder">Blueprints</NavLink>
          <NavLink to="/builder2">Builder V2 <sup>β</sup></NavLink>
          <NavLink to="/gallery">Gallery</NavLink>
          <NavLink to="/tech">Tech Tree</NavLink>
          <NavLink to="/contracts">Contracts</NavLink>
        </nav>
        <div className="topbar-tag">playtest data · unofficial</div>
      </header>
      <main className="main">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/map" element={<MapPage />} />
          <Route path="/loot" element={<Loot />} />
          <Route path="/items" element={<Navigate to="/loot" replace />} />
          <Route path="/crafting" element={<Crafting />} />
          <Route path="/builder" element={<Builder />} />
          <Route path="/builder2" element={<BuilderV2 />} />
          <Route path="/gallery" element={<Gallery />} />
          <Route path="/moderate" element={<Moderate />} />
          <Route path="/tech" element={<TechTree />} />
          <Route path="/contracts" element={<Contracts />} />
        </Routes>
      </main>
    </div>
  )
}
