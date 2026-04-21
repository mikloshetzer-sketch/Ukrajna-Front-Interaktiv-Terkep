export const FRONT_SECTORS = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      properties: {
        id: 'luhansk',
        name: 'Luhansk sector',
        shortName: 'Luhansk',
        labelLat: 49.05,
        labelLng: 38.20,
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [36.20, 50.00],
          [40.30, 50.00],
          [40.30, 48.10],
          [37.40, 48.10],
          [36.20, 49.10],
          [36.20, 50.00]
        ]]
      }
    },
    {
      type: 'Feature',
      properties: {
        id: 'donetsk',
        name: 'Donetsk sector',
        shortName: 'Donetsk',
        labelLat: 48.15,
        labelLng: 37.55,
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [36.30, 49.10],
          [39.70, 49.10],
          [39.70, 46.80],
          [36.50, 46.80],
          [36.30, 49.10]
        ]]
      }
    },
    {
      type: 'Feature',
      properties: {
        id: 'zaporizhzhia',
        name: 'Zaporizhzhia sector',
        shortName: 'Zaporizhzhia',
        labelLat: 47.25,
        labelLng: 35.75,
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [34.00, 48.30],
          [37.20, 48.30],
          [37.20, 46.20],
          [34.00, 46.20],
          [34.00, 48.30]
        ]]
      }
    },
    {
      type: 'Feature',
      properties: {
        id: 'kherson',
        name: 'Kherson sector',
        shortName: 'Kherson',
        labelLat: 46.85,
        labelLng: 33.45,
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [31.40, 47.80],
          [35.30, 47.80],
          [35.30, 45.90],
          [31.40, 45.90],
          [31.40, 47.80]
        ]]
      }
    },
    {
      type: 'Feature',
      properties: {
        id: 'kharkiv',
        name: 'Kharkiv border sector',
        shortName: 'Kharkiv',
        labelLat: 50.05,
        labelLng: 36.55,
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [35.00, 51.10],
          [38.20, 51.10],
          [38.20, 49.40],
          [35.00, 49.40],
          [35.00, 51.10]
        ]]
      }
    }
  ]
};
