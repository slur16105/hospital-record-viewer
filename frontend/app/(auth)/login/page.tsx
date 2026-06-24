import LoginForm from './LoginForm'

interface Props {
  searchParams: Promise<{ expired?: string }>
}

export default async function LoginPage({ searchParams }: Props) {
  const params = await searchParams
  return <LoginForm expired={params.expired === '1'} />
}
