import PatientRecordDetailClient from './PatientRecordDetailClient'

export default async function PatientRecordDetailPage({
  params,
}: {
  params: Promise<{ recordId: string }>
}) {
  const { recordId } = await params
  return <PatientRecordDetailClient recordId={recordId} />
}
