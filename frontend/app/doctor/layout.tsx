import RoleLayout from '@/components/RoleLayout'

export default function DoctorLayout({ children }: { children: React.ReactNode }) {
  return <RoleLayout roleName="의사">{children}</RoleLayout>
}
