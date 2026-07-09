import { NextRequest } from 'next/server'
import { proxyToBackend } from '@/lib/bff-proxy'

type Params = { params: Promise<{ id: string; fieldId: string }> }

export async function PATCH(request: NextRequest, { params }: Params) {
  const { id, fieldId } = await params
  const body = await request.json()
  return proxyToBackend(`/roles/${id}/fields/${fieldId}`, { method: 'PATCH', body })
}
