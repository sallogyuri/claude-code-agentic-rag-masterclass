import { supabase } from './supabase'

const BASE = import.meta.env.VITE_API_URL as string

async function authHeaders(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function apiFetch(path: string, init: RequestInit = {}) {
  const headers = await authHeaders()
  return fetch(`${BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...headers, ...init.headers },
  })
}
