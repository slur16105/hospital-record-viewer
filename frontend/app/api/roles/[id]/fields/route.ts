import { NextRequest } from 'next/server'
import { proxyToBackend } from '@/lib/bff-proxy'

type Params = { params: Promise<{ id: string }> }

export async function GET(_request: NextRequest, { params }: Params) {
  const { id } = await params
  return proxyToBackend(`/roles/${id}/fields`)
}

export async function POST(request: NextRequest, { params }: Params) {
  const { id } = await params
  const body = await request.json()
  return proxyToBackend(`/roles/${id}/fields`, { method: 'POST', body })
}
