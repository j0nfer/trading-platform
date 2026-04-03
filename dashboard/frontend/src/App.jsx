import Header from './components/Header'
import PortfolioCard from './components/PortfolioCard'
import PricesCard from './components/PricesCard'
import SignalsCard from './components/SignalsCard'
import WhalesCard from './components/WhalesCard'

export default function App() {
  return (
    <div className="min-h-screen bg-dark-900 text-slate-200 font-mono">
      <Header />

      <main className="p-6 max-w-7xl mx-auto">
        {/* Row 1: Portfolio (wide) + Prices */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
          <div className="lg:col-span-2">
            <PortfolioCard />
          </div>
          <div>
            <PricesCard />
          </div>
        </div>

        {/* Row 2: Signals + Whales */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <SignalsCard />
          <WhalesCard />
        </div>
      </main>

      {/* Footer */}
      <footer className="text-center py-4 text-xs text-slate-600 border-t border-dark-700 mt-6">
        Trading Platform · Jon · API:{' '}
        <a
          href="http://localhost:8000/docs"
          target="_blank"
          rel="noreferrer"
          className="text-accent-blue hover:underline"
        >
          Swagger UI
        </a>
        {' · Datos de Polymarket en tiempo real'}
      </footer>
    </div>
  )
}
