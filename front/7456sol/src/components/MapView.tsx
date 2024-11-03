import React, { useEffect, useRef } from 'react'
import L, { LatLngExpression, Map as LeafletMap, TileLayer as LeafletTileLayer, Polyline as LeafletPolyline, Marker as LeafletMarker, Icon } from 'leaflet'
import 'leaflet/dist/leaflet.css'

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

interface MapViewProps {
  route: Route
  isCreatingRoute?: boolean
  onMapClick?: (lat: number, lng: number) => void
}

export const MapView: React.FC<MapViewProps> = ({ route, isCreatingRoute, onMapClick }) => {
  const mapRef = useRef<HTMLDivElement>(null)
  const leafletMapRef = useRef<LeafletMap | null>(null)

  const defaultIcon = new Icon({
    iconUrl: '/images/marker-icon.png',
    iconRetinaUrl: '/images/marker-icon-2x.png',
    shadowUrl: '/images/marker-shadow.png',
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41]
  })

  L.Marker.prototype.options.icon = defaultIcon

  useEffect(() => {
    if (!mapRef.current) return

    const map = new LeafletMap(mapRef.current, {
      center: route?.stops[0]?.coordinates || [51.1605, 71.4704] as LatLngExpression,
      zoom: 13,
      scrollWheelZoom: true
    })

    new LeafletTileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map)

    if (isCreatingRoute) {
      map.on('click', (e) => {
        onMapClick?.(e.latlng.lat, e.latlng.lng)
      })
    }

    if (route) {
      route.segments.forEach((segment) => {
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
    }

    leafletMapRef.current = map

    return () => {
      if (leafletMapRef.current) {
        leafletMapRef.current.remove()
        leafletMapRef.current = null
      }
    }
  }, [route, isCreatingRoute, onMapClick])

  return <div ref={mapRef} style={{ height: '400px', width: '100%' }} />
} 