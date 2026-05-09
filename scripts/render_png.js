import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const ROOT_DIR = process.cwd();

const OUTPUT_DIR = path.join(ROOT_DIR, 'output');
const OUTPUT_FILE = path.join(OUTPUT_DIR, 'daily-map.png');

if (!fs.existsSync(OUTPUT_DIR)) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

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

const indexPath = path.join(ROOT_DIR, 'index.html');
const indexUrl = `file://${indexPath}`;

console.log(`Opening: ${indexUrl}`);

await page.goto(indexUrl, {
  waitUntil: 'networkidle'
});

console.log('Waiting for Leaflet map container...');

await page.waitForSelector('.leaflet-container', {
  timeout: 30000
});

console.log('Leaflet container found.');

console.log('Waiting additional time for layers and tiles...');

await page.waitForTimeout(15000);

console.log('Taking screenshot...');

await page.screenshot({
  path: OUTPUT_FILE,
  fullPage: false
});

await browser.close();

console.log(`PNG saved successfully: ${OUTPUT_FILE}`);
