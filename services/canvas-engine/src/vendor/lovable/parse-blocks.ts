// Vendored from firecrawl/open-lovable@69bd93bae7a9c97ef989eb70aabe6797fb3dac89
// Do not modify · re-vendor instead. See VENDOR_SHA.ts.

export type ParsedFile = { path: string; content: string };
export type ParsedEdit = { path: string; content: string };

const FILE_BLOCK_REGEX = /<file path="([^"]+)">([\s\S]*?)<\/file>/g;
const EDIT_BLOCK_REGEX = /<edit path="([^"]+)">([\s\S]*?)<\/edit>/g;

function parseBlocks<T extends ParsedFile | ParsedEdit>(
  text: string,
  pattern: RegExp,
): T[] {
  const results: T[] = [];

  for (const match of text.matchAll(pattern)) {
    const [, path, rawContent] = match;

    if (typeof path !== "string" || typeof rawContent !== "string") {
      continue;
    }

    results.push({
      path,
      content: rawContent.trim(),
    } as T);
  }

  return results;
}

export function parseFileBlocks(text: string): ParsedFile[] {
  return parseBlocks<ParsedFile>(text, FILE_BLOCK_REGEX);
}

export function parseEditBlocks(text: string): ParsedEdit[] {
  return parseBlocks<ParsedEdit>(text, EDIT_BLOCK_REGEX);
}

export function parseStreamedBlocks(text: string): {
  files: ParsedFile[];
  edits: ParsedEdit[];
} {
  return {
    files: parseFileBlocks(text),
    edits: parseEditBlocks(text),
  };
}
