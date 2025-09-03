import Chat from '../components/Chat'

export default function Home() {
  return (
    <main className="min-h-screen bg-slate-950 text-white p-8">
      <div className="max-w-4xl mx-auto space-y-8">
        <div className="text-center space-y-4">
          <h1 className="text-4xl font-bold text-blue-400">
            Barta
          </h1>
          <p className="text-slate-300">AI News Assistant</p>
        </div>

        <Chat />
      </div>
    </main>
  )
}