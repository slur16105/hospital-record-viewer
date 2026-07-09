import { NextRequest } from 'next/server'
import { proxyToBackend } from '@/lib/bff-proxy'

export async function GET(request: NextRequest) {
  return proxyToBackend('/users', { searchParams: request.nextUrl.searchParams })
}

export async function POST(request: NextRequest) {
  const body = await request.json()
  return proxyToBackend('/users', { method: 'POST', body })
}
