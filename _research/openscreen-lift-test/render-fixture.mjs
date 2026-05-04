// Renders a synthetic anatomy.html from the template for tour smoke-test.
// Run: node render-fixture.mjs
import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const here = path.dirname(fileURLToPath(import.meta.url));
const tpl = await readFile('C:/Users/bruke/web-audit/templates/anatomy-template.html', 'utf8');

const layers = ['ui', 'api', 'lib', 'ext', 'ui'];
const headings = ['Header', 'Sidebar nav', 'Main feed', 'Composer', 'Footer'];
const paths = ['header.tsx', 'nav/Sidebar.tsx', 'feed/List.tsx', 'compose/Editor.tsx', 'layout/Footer.tsx'];
const tops = [40, 320, 660, 1080, 1500];   // px positions of target boxes inside the dash
const heights = [120, 220, 340, 240, 100];

const renderCallout = (i) => `
  <div class="callout ${layers[i]} clickable" data-n="${i+1}" data-target="t${i+1}" data-file="${paths[i]}" data-line="${(i+1)*42}">
    <span class="no">${i+1}</span>
    <div class="hd">${headings[i]}</div>
    <div class="pth">${paths[i]}</div>
    <div class="dsc">synthetic callout for tour smoke-test</div>
  </div>`;

const left  = [0, 2, 4].map(renderCallout).join('');
const right = [1, 3].map(renderCallout).join('');

const mockup = `
  <div style="position: relative; min-height: 1700px; padding: 12px; background: linear-gradient(180deg, #0d0d12 0%, #060608 100%);">
    ${tops.map((top, i) => `
      <div class="target" id="t${i+1}" style="position: absolute; left: 24px; right: 24px; top: ${top}px; height: ${heights[i]}px; border: 1px dashed rgba(192,132,252,0.25); border-radius: 4px; padding: 14px; background: rgba(192,132,252,0.04); color: #888; font-size: 11px;">
        <span class="mono" style="color:#c084fc">#t${i+1}</span> · ${headings[i]}
      </div>
    `).join('')}
  </div>`;

const out = tpl
  .replace(/<!-- TEMPLATE:TITLE -->/g, 'Tour Smoke Test')
  .replace('<!-- TEMPLATE:SUBTITLE -->', '5 callouts · synthetic fixture · openscreen easing')
  .replace('<!-- TEMPLATE:CALLOUTS_LEFT -->', left)
  .replace('<!-- TEMPLATE:CALLOUTS_RIGHT -->', right)
  .replace('<!-- TEMPLATE:MOCKUP -->', mockup)
  .replace('<!-- TEMPLATE:CHAINS -->', '')
  .replace('<!-- TEMPLATE:SOURCE_CACHE -->', '{}');

await writeFile(path.join(here, 'anatomy-rendered.html'), out, 'utf8');
console.log('Wrote ' + path.join(here, 'anatomy-rendered.html'));
