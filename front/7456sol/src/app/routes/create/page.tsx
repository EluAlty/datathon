'use client'

import { useRouter } from 'next/navigation'
import { RouteCreator } from '@/components/RouteCreator'

export default function CreateRoute() {
  const router = useRouter()

  const handleRouteCreated = () => {
    router.push('/routes')
  }

  return (
    <div className="container mx-auto p-8">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-2xl font-bold">Create New Route</h1>
      </div>
      <RouteCreator onRouteCreated={handleRouteCreated} />
    </div>
  )
} 