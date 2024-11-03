import 'leaflet';

declare module 'react-leaflet' {
  import { MapContainer, TileLayer, Polyline, Marker, Popup, Tooltip } from 'react-leaflet';
  export { MapContainer, TileLayer, Polyline, Marker, Popup, Tooltip };
}