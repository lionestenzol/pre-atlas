// canvas-engine Phase 3 · Vite sandbox pool · in-process Vite servers per session
import { randomBytes } from 'node:crypto';
import {
  cp,
  mkdir,
  rm,
  writeFile as writeFileOnDisk,
} from 'node:fs/promises';
import path from 'node:path';
import { createServer, type ViteDevServer } from 'vite';
import tailwindcss from 'tailwindcss';
import autoprefixer from 'autoprefixer';

export interface SessionInfo {
  sessionId: string;
  port: number;
  rootDir: string;
  url: string;
  createdAt: number;
  lastActivity: number;
}

interface ActiveSession {
  info: SessionInfo;
  server: ViteDevServer;
}

export class VitePool {
  private readonly templateDir: string;
  private readonly sessionsDir: string;
  private readonly portRange: [number, number];
  private readonly sessions = new Map<string, ActiveSession>();

  public constructor(opts: {
    templateDir: string;
    sessionsDir: string;
    portRange: [number, number];
  }) {
    this.templateDir = path.resolve(opts.templateDir);
    this.sessionsDir = path.resolve(opts.sessionsDir);
    this.portRange = opts.portRange;
  }

  public async allocate(): Promise<SessionInfo> {
    await mkdir(this.sessionsDir, { recursive: true });

    const capacity = this.portRange[1] - this.portRange[0] + 1;
    if (this.sessions.size >= capacity) {
      await this.evictOldestSession();
    }

    const sessionId = this.generateSessionId();
    const rootDir = path.resolve(this.sessionsDir, sessionId);
    await cp(this.templateDir, rootDir, { recursive: true });

    let server: ViteDevServer | undefined;

    try {
      const firstPort = this.getLowestAvailablePort();
      if (firstPort === undefined) {
        throw new Error('No available Vite pool slots');
      }

      try {
        server = await this.startServer(rootDir, firstPort);
      } catch (error) {
        if (!this.isPortBindError(error)) {
          throw error;
        }

        const retryPort = this.getNextAvailablePort(firstPort + 1);
        if (retryPort === undefined) {
          throw error;
        }

        server = await this.startServer(rootDir, retryPort);
      }

      const now = Date.now();
      const info: SessionInfo = {
        sessionId,
        port: server.config.server.port ?? 0,
        rootDir,
        url: `http://localhost:${server.config.server.port ?? 0}`,
        createdAt: now,
        lastActivity: now,
      };

      this.sessions.set(sessionId, { info, server });
      return { ...info };
    } catch (error) {
      if (server !== undefined) {
        await server.close();
      }
      await rm(rootDir, { recursive: true, force: true });
      throw error;
    }
  }

  public async writeFile(
    sessionId: string,
    relativePath: string,
    content: string,
  ): Promise<void> {
    const session = this.requireSession(sessionId);
    const targetPath = this.resolveSessionPath(session.info.rootDir, relativePath);
    const parentDir = path.dirname(targetPath);

    await mkdir(parentDir, { recursive: true });
    await writeFileOnDisk(targetPath, content, 'utf8');

    session.info.lastActivity = Date.now();
  }

  public async writeFiles(
    sessionId: string,
    files: Array<{ path: string; content: string }>,
  ): Promise<void> {
    for (const file of files) {
      await this.writeFile(sessionId, file.path, file.content);
    }
  }

  public getSession(sessionId: string): SessionInfo | undefined {
    const session = this.sessions.get(sessionId);
    return session === undefined ? undefined : { ...session.info };
  }

  public async release(sessionId: string): Promise<void> {
    const session = this.sessions.get(sessionId);
    if (session === undefined) {
      return;
    }

    this.sessions.delete(sessionId);

    await session.server.close();
    await rm(session.info.rootDir, { recursive: true, force: true });
  }

  public async shutdown(): Promise<void> {
    const sessionIds = [...this.sessions.keys()];
    for (const sessionId of sessionIds) {
      await this.release(sessionId);
    }
  }

  public listActive(): SessionInfo[] {
    return [...this.sessions.values()]
      .map(({ info }) => ({ ...info }))
      .sort((left, right) => left.port - right.port);
  }

  private async evictOldestSession(): Promise<void> {
    const oldest = [...this.sessions.values()].sort(
      (left, right) => left.info.createdAt - right.info.createdAt,
    )[0];

    if (oldest === undefined) {
      throw new Error('No session available to evict');
    }

    await this.release(oldest.info.sessionId);
  }

  private generateSessionId(): string {
    for (;;) {
      const candidate = `cs-${this.randomBase36(6)}`;
      if (!this.sessions.has(candidate)) {
        return candidate;
      }
    }
  }

  private randomBase36(length: number): string {
    const alphabet = '0123456789abcdefghijklmnopqrstuvwxyz';
    const bytes = randomBytes(length);
    let value = '';

    for (const byte of bytes) {
      value += alphabet[byte % alphabet.length];
    }

    return value;
  }

  private getLowestAvailablePort(): number | undefined {
    return this.getNextAvailablePort(this.portRange[0]);
  }

  private getNextAvailablePort(startPort: number): number | undefined {
    const usedPorts = new Set(
      [...this.sessions.values()].map(({ info }) => info.port),
    );

    for (
      let port = Math.max(startPort, this.portRange[0]);
      port <= this.portRange[1];
      port += 1
    ) {
      if (!usedPorts.has(port)) {
        return port;
      }
    }

    return undefined;
  }

  private async startServer(
    rootDir: string,
    port: number,
  ): Promise<ViteDevServer> {
    const tailwindConfigPath = path.join(rootDir, 'tailwind.config.js');
    const server = await createServer({
      root: rootDir,
      server: {
        host: '127.0.0.1',
        port,
        strictPort: true,
      },
      css: {
        postcss: {
          plugins: [
            tailwindcss({ config: tailwindConfigPath }) as never,
            autoprefixer() as never,
          ],
        },
      },
    });

    try {
      await server.listen();
      return server;
    } catch (error) {
      await server.close();
      throw error;
    }
  }

  private requireSession(sessionId: string): ActiveSession {
    const session = this.sessions.get(sessionId);
    if (session === undefined) {
      throw new Error(`Unknown session: ${sessionId}`);
    }

    return session;
  }

  private resolveSessionPath(rootDir: string, relativePath: string): string {
    if (path.isAbsolute(relativePath)) {
      throw new Error(`Path traversal blocked: ${relativePath}`);
    }

    const resolvedRoot = path.resolve(rootDir);
    const targetPath = path.resolve(rootDir, relativePath);
    const relativeTarget = path.relative(resolvedRoot, targetPath);
    const isInsideRoot =
      targetPath.startsWith(resolvedRoot) &&
      relativeTarget !== '..' &&
      !relativeTarget.startsWith(`..${path.sep}`);

    if (!isInsideRoot) {
      throw new Error(`Path traversal blocked: ${relativePath}`);
    }

    return targetPath;
  }

  private isPortBindError(error: unknown): boolean {
    if (!(error instanceof Error)) {
      return false;
    }

    return /EADDRINUSE|address already in use/i.test(error.message);
  }
}
