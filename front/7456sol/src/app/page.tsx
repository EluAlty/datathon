'use client'

import React, { useState, useEffect, useRef } from 'react'
import dynamic from 'next/dynamic'
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import 'leaflet/dist/leaflet.css'
import { LatLngExpression, Map as LeafletMap, TileLayer as LeafletTileLayer, Polyline as LeafletPolyline, Marker as LeafletMarker, Popup as LeafletPopup, Icon } from 'leaflet'

// Fix for default marker icons
const defaultIcon = new Icon({
  iconUrl: '/images/marker-icon.png',
  iconRetinaUrl: '/images/marker-icon-2x.png',
  shadowUrl: '/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
})

LeafletMarker.prototype.options.icon = defaultIcon

type Stop = {
  id: string
  name: string
  predictedArrivalTime: string
  coordinates: [number, number]
}

type Segment = {
  from: Stop
  to: Stop
  travelTime: number
}

type Route = {
  id: string
  name: string
  stops: Stop[]
  segments: Segment[]
}

type UploadResponse = {
  routes?: Route[]
  error?: string
}

const API_BASE = 'http://localhost:8000'

const MapView = ({ route }: { route: Route }) => {
  const mapRef = useRef<HTMLDivElement>(null)
  const leafletMapRef = useRef<LeafletMap | null>(null)

  useEffect(() => {
    if (!mapRef.current || !route) return

    const map = new LeafletMap(mapRef.current, {
      center: route.stops[0].coordinates as LatLngExpression,
      zoom: 13,
      scrollWheelZoom: false
    })

    new LeafletTileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map)

    route.segments.forEach((segment, index) => {
      const polyline = new LeafletPolyline([segment.from.coordinates, segment.to.coordinates], {
        color: 'blue',
        weight: 3
      }).addTo(map)

      polyline.bindTooltip(`Travel time: ${segment.travelTime} min`, {
        permanent: false,
        direction: 'auto'
      })
    })

    route.stops.forEach((stop) => {
      const marker = new LeafletMarker(stop.coordinates).addTo(map)
      marker.bindPopup(`
        <div>
          <h3 style="font-weight: bold;">${stop.name}</h3>
          <p>Predicted arrival: ${stop.predictedArrivalTime}</p>
        </div>
      `)
    })

    leafletMapRef.current = map

    return () => {
      if (leafletMapRef.current) {
        leafletMapRef.current.remove()
        leafletMapRef.current = null
      }
    }
  }, [route])

  return <div ref={mapRef} style={{ height: '400px', width: '100%' }} />
}

export default function BusAnalysisInterface() {
  const [routes, setRoutes] = useState<Route[]>([])
  const [selectedRoute, setSelectedRoute] = useState<Route | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchRoutes()
  }, [])

  const fetchRoutes = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/routes`)
      const data = await response.json()
      console.log("Fetched routes:", data)
      if (data.error) {
        setError(data.error)
        return
      }
      setRoutes(data.routes || [])
    } catch (error) {
      console.error('Error fetching routes:', error)
      setError('Failed to fetch routes. Please try again.')
    }
  }

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      setFile(event.target.files[0])
      setError(null) // Clear any previous errors
    }
  }

  const handleFileUpload = async () => {
    if (!file) return

    setIsLoading(true)
    setError(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await fetch(`${API_BASE}/api/upload`, {
        method: 'POST',
        body: formData,
      })

      const data: UploadResponse = await response.json()
      console.log("Uploaded and processed routes:", data)

      if (data.error) {
        setError(`Upload failed: ${data.error}`)
        return
      }

      if (data.routes) {
        setRoutes(data.routes)
      } else {
        setError('No routes received from server')
      }
    } catch (error) {
      console.error('Error uploading file:', error)
      setError('Failed to upload file. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  const selectRoute = (route: Route) => {
    console.log('Selecting route:', route)
    setSelectedRoute(route)
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <header className="bg-blue-600 text-white px-6 py-4">
        <h1 className="text-2xl font-semibold">Astana Bus Analysis System</h1>
      </header>

      <main className="container mx-auto px-6 py-8 flex flex-col lg:flex-row gap-8">
        <Card className="w-full lg:w-1/4">
          <CardHeader>
            <CardTitle>Upload Data</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <Input 
                type="file" 
                accept=".json,.csv" 
                onChange={handleFileChange}
                className="cursor-pointer"
              />
              <Button 
                onClick={handleFileUpload} 
                disabled={!file || isLoading}
                className="w-full"
              >
                {isLoading ? 'Uploading...' : 'Upload and Process'}
              </Button>
              {error && (
                <p className="text-sm text-red-500 bg-red-50 p-2 rounded">
                  {error}
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        <div className="flex-1 space-y-8">
          <Card>
            <CardHeader>
              <CardTitle>Route Selection</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                {routes && routes.length > 0 ? (
                  routes.map((route) => (
                    <Button
                      key={route.id}
                      onClick={() => selectRoute(route)}
                      variant={selectedRoute?.id === route.id ? "default" : "outline"}
                    >
                      {route.name}
                    </Button>
                  ))
                ) : (
                  <p className="text-muted-foreground col-span-full text-center py-4">
                    No routes available. Please upload a file to load routes.
                  </p>
                )}
              </div>
            </CardContent>
          </Card>

          {selectedRoute && (
            <>
              <Card>
                <CardHeader>
                  <CardTitle>Route Map</CardTitle>
                </CardHeader>
                <CardContent>
                  <MapView route={selectedRoute} />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Predicted Arrival Times</CardTitle>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Stop Name</TableHead>
                        <TableHead>Predicted Arrival Time</TableHead>
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
            </>
          )}
        </div>
      </main>
    </div>
  )
}