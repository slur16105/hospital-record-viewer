import { NextRequest } from 'next/server'
import { proxyToBackend } from '@/lib/bff-proxy'

type Params = { params: Promise<{ id: string }> }

export async function PUT(request: NextRequest, { params }: Params) {
  const { id } = await params
  const body = await request.json()
  return proxyToBackend(`/users/${id}/roles`, { method: 'PUT', body })
}
