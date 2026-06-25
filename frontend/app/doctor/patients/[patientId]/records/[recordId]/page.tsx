import RecordDetailClient from './RecordDetailClient'

export default async function RecordDetailPage({
  params,
}: {
  params: Promise<{ patientId: string; recordId: string }>
}) {
  const { patientId, recordId } = await params
  return <RecordDetailClient patientId={patientId} recordId={recordId} />
}
