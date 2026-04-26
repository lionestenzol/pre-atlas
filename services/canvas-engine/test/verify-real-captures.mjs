import { readFileSync } from 'node:fs';
import { anatomyV1Schema } from '../src/adapter/v1-schema.ts';

const captures = [
  'C:/Users/bruke/web-audit/.tmp/hn-v1/anatomy.json',
  'C:/Users/bruke/web-audit/.tmp/example-v1/anatomy.json',
  'C:/Users/bruke/web-audit/.canvas/news.ycombinator.com/news.ycombinator.com-1b-moboruxv/anatomy.json',
  'C:/Users/bruke/web-audit/.canvas/linear.app/linear.app-7o0v19-mod91ex3/anatomy.json',
  'C:/Users/bruke/web-audit/.canvas/www.figma.com/www.figma.com-zv2v16-mobw1b4l/anatomy.json',
  'C:/Users/bruke/web-audit/.canvas/console.apify.com/console.apify.com-o2h0cy-mobnda5d/anatomy.json',
  'C:/Users/bruke/web-audit/.canvas/mail.google.com/mail.google.com-1iifhe-mobjcx3v/anatomy.json',
];

let pass = 0;
let fail = 0;
for (const path of captures) {
  try {
    const raw = JSON.parse(readFileSync(path, 'utf8'));
    const result = anatomyV1Schema.safeParse(raw);
    const tag = path.split(/[\\/]/).slice(-2).join('/');
    if (result.success) {
      pass++;
      console.log(`PASS · ${tag} · regions=${raw.regions?.length ?? 0} chains=${raw.chains?.length ?? 0}`);
    } else {
      fail++;
      console.log(`FAIL · ${tag}`);
      console.log(JSON.stringify(result.error.issues.slice(0, 3), null, 2));
    }
  } catch (e) {
    fail++;
    console.log(`ERROR · ${path} · ${e.message}`);
  }
}
console.log(`\nTotal: ${pass} pass · ${fail} fail`);
process.exit(fail === 0 ? 0 : 1);
