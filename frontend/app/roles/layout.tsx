import RoleLayout from '@/components/RoleLayout'

export default function RolesLayout({ children }: { children: React.ReactNode }) {
  return <RoleLayout roleName="관리자">{children}</RoleLayout>
}
