import { NextRequest } from 'next/server'
import { proxyToBackend } from '@/lib/bff-proxy'

type Params = { params: Promise<{ id: string }> }

export async function GET(_request: NextRequest, { params }: Params) {
  const { id } = await params
  return proxyToBackend(`/roles/${id}`)
}

export async function PATCH(request: NextRequest, { params }: Params) {
  const { id } = await params
  const body = await request.json()
  return proxyToBackend(`/roles/${id}`, { method: 'PATCH', body })
}

export async function DELETE(_request: NextRequest, { params }: Params) {
  const { id } = await params
  return proxyToBackend(`/roles/${id}`, { method: 'DELETE' })
}
