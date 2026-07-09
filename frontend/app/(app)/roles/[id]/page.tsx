import RoleDetailClient from './RoleDetailClient'

export default async function RoleDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  return <RoleDetailClient roleId={id} />
}
