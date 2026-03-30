import { AuthGuard } from './components/AuthGuard'
import { ChatPage } from './pages/ChatPage'

export default function App() {
  return (
    <AuthGuard>
      <ChatPage />
    </AuthGuard>
  )
}
