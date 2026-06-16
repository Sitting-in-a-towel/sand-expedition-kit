import { Link } from 'react-router-dom'
import { locations, tables, items, recipes, parts } from '../lib/data.js'

const LINKS = [
  {
    to: '/map',
    glyph: '◈',
    title: 'Operations Board',
    desc: 'Every named island, wreck and rock formation — what loot each one holds, on a tactical sector board.',
  },
  {
    to: '/loot',
    glyph: '▤',
    title: 'Loot',
    desc: `Item-first lookup with ${tables.length} datamined container tables behind it — where everything drops, in which tier zones, per game mode.`,
  },
  {
    to: '/crafting',
    glyph: '⚒',
    title: 'Crafting Manual',
    desc: 'Workbench recipes — exact inputs, outputs and craft times, straight from the game files.',
  },
  {
    to: '/builder',
    glyph: '▦',
    title: 'Trampler Blueprints',
    desc: 'Plan a build deck-by-deck on the real compartment grid, with a full parts manifest you can share.',
  },
]

export default function Home() {
  return (
    <>
      <section className="hero" style={{ animation: 'rise .5s cubic-bezier(.16,1,.3,1) both' }}>
        <div className="hero-stripe" />
        <h1>
          Raid the dunes
          <br />
          <span className="accent">with a plan.</span>
        </h1>
        <p>
          Unofficial community field kit for SAND. Every location, loot table, recipe and
          compartment in this kit was datamined from the playtest files — no guesswork, no memory
          reading, fully offline.
        </p>
        <div className="stat-row stagger">
          <div className="stat">
            <div className="n">{locations.length}</div>
            <div className="l">Named locations</div>
          </div>
          <div className="stat">
            <div className="n">{tables.length}</div>
            <div className="l">Loot tables</div>
          </div>
          <div className="stat">
            <div className="n">{items.length}</div>
            <div className="l">Items indexed</div>
          </div>
          <div className="stat">
            <div className="n">{recipes.length}</div>
            <div className="l">Recipes</div>
          </div>
          <div className="stat">
            <div className="n">{parts.length}</div>
            <div className="l">Trampler parts</div>
          </div>
        </div>
      </section>

      <div className="section-label">Field manual</div>
      <div className="home-links stagger">
        {LINKS.map((l) => (
          <Link key={l.to} to={l.to} className="home-link">
            <span className="hl-glyph">{l.glyph}</span>
            <h3>{l.title}</h3>
            <p>{l.desc}</p>
          </Link>
        ))}
      </div>

      <div className="footnote">
        SAND © Hologryph / TowerHaus / tinyBuild. This is an unofficial fan project built from
        static playtest files (2026-06-10). Values may change at launch on 22 June.
      </div>
    </>
  )
}
