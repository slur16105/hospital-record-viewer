import PatientRecordsClient from './PatientRecordsClient'

export default async function PatientRecordsPage({
  params,
}: {
  params: Promise<{ patientId: string }>
}) {
  const { patientId } = await params
  return <PatientRecordsClient patientId={patientId} />
}
