import { parseStreamedBlocks } from './parse-blocks.js';
import { buildSystemPrompt, type BuildSystemPromptOptions } from './system-prompt.js';

export interface GenerateOptions {
  url?: string;
  prompt?: string;
  isEdit?: boolean;
  conversationContext?: string;
}

export type StreamEvent =
  | { type: 'status'; message: string }
  | { type: 'file'; path: string; content: string }
  | { type: 'done'; fileCount: number };

const STUB_RESPONSE = `Generating React clone for Vite app...

<file path="src/App.jsx">
import { Header } from './components/Header';
import { Hero } from './components/Hero';
import { Footer } from './components/Footer';

export default function App() {
  return (
    <div className="min-h-screen bg-white">
      <Header />
      <Hero />
      <Footer />
    </div>
  );
}
</file>

<file path="src/components/Header.jsx">
export function Header() {
  return (
    <header className="bg-white border-b border-gray-200">
      <nav className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
        <div className="text-xl font-bold text-gray-900">Stub Clone</div>
        <a href="#" className="text-blue-500 hover:text-blue-700">Home</a>
      </nav>
    </header>
  );
}
</file>

<file path="src/components/Hero.jsx">
export function Hero() {
  return (
    <section className="max-w-7xl mx-auto px-4 py-24 text-center">
      <h1 className="text-5xl font-bold text-gray-900">Phase 1 stub</h1>
      <p className="mt-4 text-lg text-gray-600">
        Real LLM integration ships in Phase 3.
      </p>
    </section>
  );
}
</file>

<file path="src/components/Footer.jsx">
export function Footer() {
  return (
    <footer className="bg-gray-100 py-8 mt-16">
      <div className="max-w-7xl mx-auto px-4 text-center text-sm text-gray-500">
        canvas-engine · Phase 1 · Foundation
      </div>
    </footer>
  );
}
</file>
`;

export async function* generateStub(opts: GenerateOptions): AsyncGenerator<StreamEvent> {
  const promptOpts: BuildSystemPromptOptions = {
    isEdit: opts.isEdit ?? false,
    conversationContext: opts.conversationContext ?? '',
    editContext: null,
  };
  const systemPromptPreview = buildSystemPrompt(promptOpts).slice(0, 80).replace(/\n/g, ' ');

  yield {
    type: 'status',
    message: `phase-1-stub · url=${opts.url ?? '(none)'} · prompt-preview="${systemPromptPreview}..."`,
  };

  const { files } = parseStreamedBlocks(STUB_RESPONSE);
  for (const file of files) {
    await new Promise<void>((resolve) => setTimeout(resolve, 30));
    yield { type: 'file', path: file.path, content: file.content };
  }

  yield { type: 'done', fileCount: files.length };
}
