import { NextRequest } from 'next/server'
import { proxyToBackend } from '@/lib/bff-proxy'

export async function GET() {
  return proxyToBackend('/roles')
}

export async function POST(request: NextRequest) {
  const body = await request.json()
  return proxyToBackend('/roles', { method: 'POST', body })
}
