import React, { useState } from 'react'
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { MapView } from "./MapView"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

type RouteStop = {
  id: string
  name: string
  coordinates: [number, number]
  sequence: number
  predictedArrivalTime: string
}

export function RouteCreator({ onRouteCreated }: { onRouteCreated: () => void }) {
  const [routeName, setRouteName] = useState('')
  const [startTime, setStartTime] = useState('06:00')
  const [endTime, setEndTime] = useState('23:00')
  const [newStops, setNewStops] = useState<RouteStop[]>([])

  const handleMapClick = (lat: number, lng: number) => {
    const newStop: RouteStop = {
      id: `stop-${newStops.length + 1}`,
      name: `Stop ${newStops.length + 1}`,
      coordinates: [lat, lng],
      sequence: newStops.length + 1,
      predictedArrivalTime: calculateScheduledTime(newStops.length + 1)
    }
    setNewStops([...newStops, newStop])
  }

  const calculateScheduledTime = (sequence: number): string => {
    const startMinutes = parseInt(startTime.split(':')[0]) * 60 + parseInt(startTime.split(':')[1])
    const endMinutes = parseInt(endTime.split(':')[0]) * 60 + parseInt(endTime.split(':')[1])
    const totalDuration = endMinutes - startMinutes
    const interval = totalDuration / (newStops.length + 1)
    const stopMinutes = startMinutes + (interval * sequence)
    const hours = Math.floor(stopMinutes / 60)
    const minutes = Math.floor(stopMinutes % 60)
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`
  }

  const createRoute = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/routes/create', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: routeName,
          stops: newStops.map(stop => ({
            name: stop.name,
            latitude: stop.coordinates[0],
            longitude: stop.coordinates[1],
            scheduled_time: stop.predictedArrivalTime
          }))
        }),
      })

      const data = await response.json()
      if (data.error) {
        alert(data.error)
        return
      }

      onRouteCreated()
    } catch (error) {
      console.error('Error creating route:', error)
      alert('Failed to create route')
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <Input
          placeholder="Название маршрута"
          value={routeName}
          onChange={(e) => setRouteName(e.target.value)}
        />
        
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm font-medium">Время начала</label>
            <Input
              type="time"
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
            />
          </div>
          <div>
            <label className="text-sm font-medium">Время окончания</label>
            <Input
              type="time"
              value={endTime}
              onChange={(e) => setEndTime(e.target.value)}
            />
          </div>
        </div>

        <div className="h-[400px] border rounded-lg overflow-hidden">
          <MapView
            route={{
              id: 'new',
              name: routeName || 'New Route',
              stops: newStops,
              segments: []
            }}
            isCreatingRoute={true}
            onMapClick={handleMapClick}
          />
        </div>

        {newStops.length > 0 && (
          <div className="space-y-2">
            <h3 className="font-semibold">Добавленные остановки:</h3>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>№</TableHead>
                  <TableHead>Название</TableHead>
                  <TableHead>Координаты</TableHead>
                  <TableHead>Время прибытия</TableHead>
                  <TableHead>Действия</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {newStops.map((stop, index) => (
                  <TableRow key={stop.id}>
                    <TableCell>{index + 1}</TableCell>
                    <TableCell>{stop.name}</TableCell>
                    <TableCell>
                      {stop.coordinates[0].toFixed(4)}, {stop.coordinates[1].toFixed(4)}
                    </TableCell>
                    <TableCell>{stop.predictedArrivalTime}</TableCell>
                    <TableCell>
                      <Button 
                        variant="destructive" 
                        size="sm"
                        onClick={() => {
                          const updatedStops = newStops.filter(s => s.id !== stop.id)
                          setNewStops(updatedStops)
                        }}
                      >
                        Удалить
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        <Button 
          onClick={() => createRoute()}
          disabled={newStops.length < 2 || !routeName}
          className="w-full"
        >
          Создать маршрут
        </Button>
      </div>
    </div>
  )
} 