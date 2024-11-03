'use client'

import React, { useState, useEffect } from 'react'
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import Link from 'next/link'
import { MapView } from "@/components/MapView"

const API_BASE = 'http://localhost:8000'

type RouteStop = {
  id: string
  name: string
  coordinates: [number, number]
  sequence: number
  predictedArrivalTime: string
}

type RouteSegment = {
  from: {
    id: string
    name: string
    coordinates: [number, number]
    predictedArrivalTime: string
  }
  to: {
    id: string
    name: string
    coordinates: [number, number]
    predictedArrivalTime: string
  }
  travelTime: number
}

type RouteData = {
  id: string
  name: string
  startTime: string
  endTime: string
  stops: RouteStop[]
  segments: RouteSegment[]
}

export default function RoutesPage() {
  const [routes, setRoutes] = useState<RouteData[]>([])
  const [selectedRoute, setSelectedRoute] = useState<RouteData | null>(null)

  useEffect(() => {
    fetchRoutes()
  }, [])

  const fetchRoutes = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/routes`)
      const data = await response.json()
      const routesWithSegments = (data.routes || []).map((route: RouteData) => ({
        ...route,
        segments: route.segments || route.stops.slice(0, -1).map((stop, index) => ({
          from: {
            id: stop.id,
            name: stop.name,
            coordinates: stop.coordinates,
            predictedArrivalTime: stop.predictedArrivalTime
          },
          to: {
            id: route.stops[index + 1].id,
            name: route.stops[index + 1].name,
            coordinates: route.stops[index + 1].coordinates,
            predictedArrivalTime: route.stops[index + 1].predictedArrivalTime
          },
          travelTime: 5
        }))
      }))
      setRoutes(routesWithSegments)
    } catch (error) {
      console.error('Error fetching routes:', error)
    }
  }

  const downloadAllRoutesCSV = () => {
    const csvContent = [
      'route_id,route_name,stop_id,stop_name,latitude,longitude,sequence,scheduled_time',
      ...routes.flatMap(route => 
        route.stops.map(stop => 
          `${route.id},${route.name},${stop.id},${stop.name},${stop.coordinates[0]},${stop.coordinates[1]},${stop.sequence},${stop.predictedArrivalTime}`
        )
      )
    ].join('\n')

    const blob = new Blob([csvContent], { type: 'text/csv' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'all_routes.csv'
    a.click()
  }

  const deleteRoute = async (routeId: string) => {
    try {
      await fetch(`${API_BASE}/api/routes/${routeId}`, {
        method: 'DELETE'
      })
      setRoutes(routes.filter(r => r.id !== routeId))
      if (selectedRoute?.id === routeId) {
        setSelectedRoute(null)
      }
    } catch (error) {
      console.error('Error deleting route:', error)
    }
  }

  return (
    <div className="container mx-auto p-8">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-2xl font-bold">Routes Management</h1>
        <div className="space-x-4">
          <Button asChild>
            <Link href="/routes/create">Create New Route</Link>
          </Button>
          <Button 
            variant="outline" 
            onClick={downloadAllRoutesCSV}
            disabled={routes.length === 0}
          >
            Download All Routes
          </Button>
        </div>
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <Card>
          <CardHeader>
            <CardTitle>Available Routes</CardTitle>
          </CardHeader>
          <CardContent>
            {routes.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Stops</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {routes.map((route) => (
                    <TableRow 
                      key={route.id}
                      className={selectedRoute?.id === route.id ? "bg-muted" : ""}
                    >
                      <TableCell>{route.name}</TableCell>
                      <TableCell>{route.stops.length} stops</TableCell>
                      <TableCell>
                        <div className="space-x-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setSelectedRoute(route)}
                          >
                            View
                          </Button>
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => deleteRoute(route.id)}
                          >
                            Delete
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                No routes available. Create a new route to get started.
              </div>
            )}
          </CardContent>
        </Card>

        {selectedRoute && (
          <Card>
            <CardHeader>
              <CardTitle>Route Details: {selectedRoute.name}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-[400px] mb-4">
                <MapView route={selectedRoute} />
              </div>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Stop Name</TableHead>
                    <TableHead>Predicted Arrival</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {selectedRoute.stops.map((stop) => (
                    <TableRow key={stop.id}>
                      <TableCell>{stop.name}</TableCell>
                      <TableCell>{stop.predictedArrivalTime}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
} 