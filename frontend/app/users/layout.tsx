import RoleLayout from '@/components/RoleLayout'

export default function UsersLayout({ children }: { children: React.ReactNode }) {
  return <RoleLayout roleName="관리자">{children}</RoleLayout>
}
