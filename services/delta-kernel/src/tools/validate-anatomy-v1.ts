/**
 * AnatomyV1 schema validator.
 *
 * Loads contracts/schemas/AnatomyV1.v1.json and validates every supplied
 * anatomy.json capture against it. Exits 0 iff every file passes.
 *
 * Usage:
 *   tsx src/tools/validate-anatomy-v1.ts                      # default fixture set
 *   tsx src/tools/validate-anatomy-v1.ts --path <file> ...    # override
 */

import * as fs from 'fs';
import * as path from 'path';
import * as url from 'url';
import Ajv, { ErrorObject, ValidateFunction } from 'ajv';

const __filename = url.fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const REPO_ROOT = path.resolve(__dirname, '..', '..', '..', '..');
const SCHEMA_PATH = path.join(REPO_ROOT, 'contracts', 'schemas', 'AnatomyV1.v1.json');

const DEFAULT_CAPTURES: ReadonlyArray<string> = [
  'C:/Users/bruke/web-audit/.tmp/hn-v1/anatomy.json',
  'C:/Users/bruke/web-audit/.tmp/example-v1/anatomy.json',
  'C:/Users/bruke/web-audit/.canvas/news.ycombinator.com/news.ycombinator.com-1b-moboruxv/anatomy.json',
  'C:/Users/bruke/web-audit/.canvas/linear.app/linear.app-7o0v19-mod91ex3/anatomy.json',
  'C:/Users/bruke/web-audit/.canvas/www.figma.com/www.figma.com-zv2v16-mobw1b4l/anatomy.json',
  'C:/Users/bruke/web-audit/.canvas/console.apify.com/console.apify.com-o2h0cy-mobnda5d/anatomy.json',
  'C:/Users/bruke/web-audit/.canvas/mail.google.com/mail.google.com-1iifhe-mobjcx3v/anatomy.json',
];

interface CliOptions {
  paths: ReadonlyArray<string>;
}

function parseArgs(argv: ReadonlyArray<string>): CliOptions {
  const overrides: string[] = [];
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--path') {
      const next = argv[i + 1];
      if (!next) {
        console.error('error: --path requires a value');
        process.exit(2);
      }
      overrides.push(next);
      i++;
    }
  }
  return { paths: overrides.length > 0 ? overrides : DEFAULT_CAPTURES };
}

function getErrorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

function loadAndCompileSchema(): ValidateFunction {
  let raw: string;
  try {
    raw = fs.readFileSync(SCHEMA_PATH, 'utf8');
  } catch (err: unknown) {
    console.error(`error: cannot read schema at ${SCHEMA_PATH}: ${getErrorMessage(err)}`);
    process.exit(2);
  }
  let schema: unknown;
  try {
    schema = JSON.parse(raw);
  } catch (err: unknown) {
    console.error(`error: schema is not valid JSON: ${getErrorMessage(err)}`);
    process.exit(2);
  }
  if (typeof schema !== 'object' || schema === null) {
    console.error(`error: schema must be a JSON object, got ${typeof schema}`);
    process.exit(2);
  }
  const ajv = new Ajv({ strict: false, allErrors: true });
  try {
    return ajv.compile(schema as Record<string, unknown>);
  } catch (err: unknown) {
    console.error(`error: schema failed to compile: ${getErrorMessage(err)}`);
    process.exit(2);
  }
}

function formatErrors(errors: ReadonlyArray<ErrorObject> | null | undefined): string {
  if (!errors || errors.length === 0) return '(no error detail)';
  return errors
    .slice(0, 10)
    .map((e) => `    ${e.instancePath || '<root>'} ${e.message ?? ''} ${JSON.stringify(e.params)}`)
    .join('\n');
}

interface FileResult {
  filePath: string;
  pass: boolean;
  detail: string;
}

function validateOne(validate: ValidateFunction, filePath: string): FileResult {
  let raw: string;
  try {
    raw = fs.readFileSync(filePath, 'utf8');
  } catch (err: unknown) {
    const code = (err as NodeJS.ErrnoException)?.code;
    const detail = code === 'ENOENT' ? '    file not found' : `    read error: ${getErrorMessage(err)}`;
    return { filePath, pass: false, detail };
  }
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch (err: unknown) {
    return { filePath, pass: false, detail: `    JSON parse error: ${getErrorMessage(err)}` };
  }
  const ok = validate(data);
  if (ok) return { filePath, pass: true, detail: '' };
  return { filePath, pass: false, detail: formatErrors(validate.errors) };
}

function main(): void {
  const { paths } = parseArgs(process.argv.slice(2));
  const validate = loadAndCompileSchema();

  console.log(`AnatomyV1 validator`);
  console.log(`  schema: ${path.relative(REPO_ROOT, SCHEMA_PATH)}`);
  console.log(`  files:  ${paths.length}`);
  console.log('');

  let passed = 0;
  for (const filePath of paths) {
    const result = validateOne(validate, filePath);
    if (result.pass) {
      passed++;
      console.log(`  PASS  ${filePath}`);
    } else {
      console.log(`  FAIL  ${filePath}`);
      console.log(result.detail);
    }
  }

  console.log('');
  console.log(`${passed}/${paths.length} passed`);
  process.exit(passed === paths.length ? 0 : 1);
}

main();
