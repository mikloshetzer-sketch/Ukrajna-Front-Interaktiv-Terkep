import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';
import http from 'http';

const ROOT_DIR = process.cwd();

const OUTPUT_DIR = path.join(ROOT_DIR, 'output');
const OUTPUT_FILE = path.join(OUTPUT_DIR, 'daily-map.png');

const PORT = 4173;
const HOST = '127.0.0.1';

if (!fs.existsSync(OUTPUT_DIR)) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

function getMimeType(filePath) {
  const ext = path.extname(filePath).toLowerCase();

  const mimeTypes = {
    '.html': 'text/html; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.mjs': 'application/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.svg': 'image/svg+xml',
    '.webp': 'image/webp',
    '.geojson': 'application/geo+json; charset=utf-8'
  };

  return mimeTypes[ext] || 'application/octet-stream';
}

function startStaticServer() {
  const server = http.createServer((req, res) => {
    try {
      const requestUrl = new URL(req.url, `http://${HOST}:${PORT}`);
      let requestedPath = decodeURIComponent(requestUrl.pathname);

      if (requestedPath === '/') {
        requestedPath = '/index.html';
      }

      const filePath = path.normalize(path.join(ROOT_DIR, requestedPath));

      if (!filePath.startsWith(ROOT_DIR)) {
        res.writeHead(403);
        res.end('Forbidden');
        return;
      }

      if (!fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
        res.writeHead(404);
        res.end(`Not found: ${requestedPath}`);
        return;
      }

      const fileContent = fs.readFileSync(filePath);
      const mimeType = getMimeType(filePath);

      res.writeHead(200, {
        'Content-Type': mimeType,
        'Access-Control-Allow-Origin': '*',
        'Cache-Control': 'no-store'
      });

      res.end(fileContent);
    } catch (error) {
      res.writeHead(500);
      res.end(String(error));
    }
  });

  return new Promise((resolve) => {
    server.listen(PORT, HOST, () => {
      console.log(`Static server running at http://${HOST}:${PORT}`);
      resolve(server);
    });
  });
}

async function switchToCartoLight(page) {
  console.log('Trying to switch base map to CARTO Light...');

  await page.evaluate(() => {
    const labels = Array.from(document.querySelectorAll('label'));

    const cartoLabel = labels.find((label) =>
      label.textContent &&
      label.textContent.toLowerCase().includes('carto light')
    );

    if (cartoLabel) {
      const input = cartoLabel.querySelector('input[type="radio"]');

      if (input) {
        input.click();
        return;
      }

      cartoLabel.click();
      return;
    }

    const inputs = Array.from(document.querySelectorAll('input[type="radio"]'));

    const cartoInput = inputs.find((input) => {
      const parentText = input.parentElement?.textContent?.toLowerCase() || '';
      return parentText.includes('carto light');
    });

    if (cartoInput) {
      cartoInput.click();
    }
  });

  await page.waitForTimeout(5000);

  console.log('Base map switch attempt completed.');
}

async function hideControlPanels(page) {
  console.log('Hiding side panels and non-map layout elements...');

  await page.addStyleTag({
    content: `
      body {
        margin: 0 !important;
        padding: 0 !important;
        overflow: hidden !important;
        background: #ffffff !important;
      }

      .app-shell,
      .layout,
      .page,
      main,
      #app {
        margin: 0 !important;
        padding: 0 !important;
      }

      aside,
      .sidebar,
      .side-panel,
      .control-panel,
      .controls,
      .left-panel,
      .panel,
      .toolbar,
      .header,
      header,
      footer {
        display: none !important;
      }

      .map-wrap,
      .map-container,
      #map,
      .leaflet-container {
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        width: 1600px !important;
        height: 1000px !important;
        margin: 0 !important;
        padding: 0 !important;
        z-index: 999999 !important;
      }

      .leaflet-control-zoom {
        display: none !important;
      }
    `
  });

  await page.waitForTimeout(2000);

  console.log('Panels hidden.');
}

const server = await startStaticServer();

const browser = await chromium.launch({
  headless: true
});

const page = await browser.newPage({
  viewport: {
    width: 1600,
    height: 1000
  },
  deviceScaleFactor: 1
});

page.on('console', (msg) => {
  console.log(`[browser console] ${msg.type()}: ${msg.text()}`);
});

page.on('pageerror', (error) => {
  console.log(`[browser error] ${error.message}`);
});

const url = `http://${HOST}:${PORT}/index.html`;

console.log(`Opening: ${url}`);

await page.goto(url, {
  waitUntil: 'networkidle',
  timeout: 60000
});

console.log('Waiting for Leaflet map container...');

try {
  await page.waitForSelector('.leaflet-container', {
    timeout: 60000,
    state: 'visible'
  });

  console.log('Leaflet container found.');
} catch (error) {
  console.log('Leaflet container was not found in time. Screenshot will still be created for debugging.');
}

console.log('Waiting for map layers and data...');

await page.waitForTimeout(10000);

await switchToCartoLight(page);

console.log('Waiting after CARTO Light switch...');

await page.waitForTimeout(8000);

await hideControlPanels(page);

console.log('Waiting after layout cleanup...');

await page.waitForTimeout(5000);

const mapElement = await page.$('.leaflet-container');

if (!mapElement) {
  console.log('Map element not found. Taking full page screenshot as fallback.');

  await page.screenshot({
    path: OUTPUT_FILE,
    fullPage: false
  });
} else {
  console.log('Taking map-only screenshot...');

  await mapElement.screenshot({
    path: OUTPUT_FILE
  });
}

await browser.close();
server.close();

console.log(`PNG saved successfully: ${OUTPUT_FILE}`);
