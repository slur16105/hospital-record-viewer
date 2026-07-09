import { NextRequest } from 'next/server'
import { proxyToBackend } from '@/lib/bff-proxy'

type Params = { params: Promise<{ id: string }> }

export async function GET(_request: NextRequest, { params }: Params) {
  const { id } = await params
  return proxyToBackend(`/users/${id}`)
}

export async function PATCH(request: NextRequest, { params }: Params) {
  const { id } = await params
  const body = await request.json()
  return proxyToBackend(`/users/${id}`, { method: 'PATCH', body })
}
