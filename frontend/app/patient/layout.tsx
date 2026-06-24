import RoleLayout from '@/components/RoleLayout'

export default function PatientLayout({ children }: { children: React.ReactNode }) {
  return <RoleLayout roleName="환자">{children}</RoleLayout>
}
