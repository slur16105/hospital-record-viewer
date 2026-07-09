import RecordCreateClient from './RecordCreateClient'

export default async function RecordCreatePage({
  params,
}: {
  params: Promise<{ patientId: string }>
}) {
  const { patientId } = await params
  return <RecordCreateClient patientId={patientId} />
}
