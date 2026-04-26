import { readFileSync } from 'node:fs';
import Ajv from 'ajv';

const schemaPath = 'C:/Users/bruke/Pre Atlas/contracts/schemas/AnatomyV1.v1.json';
const captures = [
  'C:/Users/bruke/web-audit/.tmp/hn-v1/anatomy.json',
  'C:/Users/bruke/web-audit/.tmp/example-v1/anatomy.json',
  'C:/Users/bruke/web-audit/.canvas/news.ycombinator.com/news.ycombinator.com-1b-moboruxv/anatomy.json',
  'C:/Users/bruke/web-audit/.canvas/linear.app/linear.app-7o0v19-mod91ex3/anatomy.json',
  'C:/Users/bruke/web-audit/.canvas/www.figma.com/www.figma.com-zv2v16-mobw1b4l/anatomy.json',
  'C:/Users/bruke/web-audit/.canvas/console.apify.com/console.apify.com-o2h0cy-mobnda5d/anatomy.json',
  'C:/Users/bruke/web-audit/.canvas/mail.google.com/mail.google.com-1iifhe-mobjcx3v/anatomy.json',
];

const schema = JSON.parse(readFileSync(schemaPath, 'utf8'));
const ajv = new Ajv({ strict: false, allErrors: true });
const validate = ajv.compile(schema);

let pass = 0, fail = 0;
for (const path of captures) {
  const raw = JSON.parse(readFileSync(path, 'utf8'));
  const tag = path.split(/[\\/]/).slice(-2).join('/');
  if (validate(raw)) {
    pass++;
    console.log(`PASS · ${tag} · regions=${raw.regions?.length ?? 0} chains=${raw.chains?.length ?? 0}`);
  } else {
    fail++;
    console.log(`FAIL · ${tag}`);
    console.log(JSON.stringify(validate.errors?.slice(0, 3), null, 2));
  }
}
console.log(`\nTotal: ${pass} pass · ${fail} fail (against contracts/schemas/AnatomyV1.v1.json via ajv)`);
process.exit(fail === 0 ? 0 : 1);
