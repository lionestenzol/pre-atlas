import {
  AbsoluteFill,
  Easing,
  Series,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';

export interface MainProps {
  targetLabel: string;
  pullPrompt: string;
  outputFile: string;
}

const palette = {
  bg: '#0b0d10',
  panel: '#14171c',
  ink: '#f5f7fa',
  dim: '#8a92a0',
  accent: '#7cf2b0',
  slot: '#1b1f26',
  slotBorder: '#2b3240',
};

const baseTextStyle: React.CSSProperties = {
  fontFamily: 'system-ui, -apple-system, sans-serif',
  color: palette.ink,
};

export function Main({ targetLabel, pullPrompt, outputFile }: MainProps) {
  return (
    <AbsoluteFill style={{ background: palette.bg }}>
      <Series>
        <Series.Sequence durationInFrames={90}>
          <TitleScene target={targetLabel} />
        </Series.Sequence>

        <Series.Sequence durationInFrames={210}>
          <ClipSlot
            beat="1 / 4"
            label="Pull this page"
            hint={`Playwright: browser.newContext({ recordVideo: { dir: "clips/pull" } })`}
            target={targetLabel}
          />
        </Series.Sequence>

        <Series.Sequence durationInFrames={150}>
          <ClipSlot
            beat="2 / 4"
            label="Open in canvas"
            hint={`opens http://localhost:8088/canvas?file=${outputFile}`}
          />
        </Series.Sequence>

        <Series.Sequence durationInFrames={300}>
          <ClipSlot
            beat="3 / 4"
            label="Edit with Claude"
            hint={`prompt: "${pullPrompt}"`}
          />
        </Series.Sequence>

        <Series.Sequence durationInFrames={150}>
          <OutroScene outputFile={outputFile} />
        </Series.Sequence>
      </Series>
    </AbsoluteFill>
  );
}

interface TitleSceneProps {
  target: string;
}

function TitleScene({ target }: TitleSceneProps) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const opacity = interpolate(frame, [0, 20], [0, 1], { extrapolateRight: 'clamp' });
  const scale = spring({ fps, frame, from: 0.96, to: 1, config: { damping: 14 } });

  return (
    <AbsoluteFill
      style={{
        alignItems: 'center',
        justifyContent: 'center',
        background: palette.bg,
        ...baseTextStyle,
      }}
    >
      <div style={{ opacity, transform: `scale(${scale})`, textAlign: 'center' }}>
        <div style={{ fontSize: 28, color: palette.dim, letterSpacing: 8, textTransform: 'uppercase' }}>
          Canvas
        </div>
        <div style={{ fontSize: 144, fontWeight: 700, marginTop: 24 }}>
          Pull &rarr; Edit &rarr; Ship
        </div>
        <div style={{ fontSize: 32, color: palette.dim, marginTop: 32 }}>
          demo target: {target}
        </div>
      </div>
    </AbsoluteFill>
  );
}

interface ClipSlotProps {
  beat: string;
  label: string;
  hint: string;
  target?: string;
}

function ClipSlot({ beat, label, hint, target }: ClipSlotProps) {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  // Screen-Studio feel — ported from openscreen mathUtils.ts.
  // cubicBezier(0.16, 1, 0.3, 1) is snappy-then-slow, the curve OpenScreen
  // uses for its zoom pan. Same control points, native Remotion impl.
  const entry = interpolate(frame, [0, 16], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  const exit = interpolate(
    frame,
    [durationInFrames - 12, durationInFrames],
    [1, 0],
    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
  );
  const opacity = Math.min(entry, exit);
  const lift = interpolate(entry, [0, 1], [16, 0]);

  return (
    <AbsoluteFill style={{ background: palette.bg, ...baseTextStyle }}>
      <div
        style={{
          position: 'absolute',
          top: 72,
          left: 96,
          opacity,
          transform: `translateY(${lift}px)`,
        }}
      >
        <div style={{ fontSize: 24, color: palette.accent, letterSpacing: 4 }}>{beat}</div>
        <div style={{ fontSize: 72, fontWeight: 600, marginTop: 12 }}>{label}</div>
        {target && (
          <div style={{ fontSize: 28, color: palette.dim, marginTop: 8 }}>on {target}</div>
        )}
      </div>

      <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
        <div
          style={{
            width: 1600,
            height: 780,
            background: palette.slot,
            border: `2px dashed ${palette.slotBorder}`,
            borderRadius: 16,
            opacity,
            transform: `translateY(${lift}px)`,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 20,
          }}
        >
          <div style={{ fontSize: 32, color: palette.dim }}>clip slot</div>
          <div
            style={{
              fontFamily: 'ui-monospace, Menlo, Consolas, monospace',
              fontSize: 22,
              color: palette.ink,
              maxWidth: 1400,
              textAlign: 'center',
              lineHeight: 1.5,
            }}
          >
            {hint}
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
}

interface OutroSceneProps {
  outputFile: string;
}

function OutroScene({ outputFile }: OutroSceneProps) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const opacity = interpolate(frame, [0, 24], [0, 1], { extrapolateRight: 'clamp' });
  const scale = spring({ fps, frame, from: 0.9, to: 1, config: { damping: 10 } });

  return (
    <AbsoluteFill
      style={{
        alignItems: 'center',
        justifyContent: 'center',
        background: palette.bg,
        ...baseTextStyle,
      }}
    >
      <div style={{ opacity, transform: `scale(${scale})`, textAlign: 'center' }}>
        <div style={{ fontSize: 36, color: palette.accent, letterSpacing: 4 }}>SHIPPED</div>
        <div
          style={{
            fontFamily: 'ui-monospace, Menlo, Consolas, monospace',
            fontSize: 56,
            marginTop: 24,
            color: palette.ink,
          }}
        >
          {outputFile}
        </div>
        <div style={{ fontSize: 28, color: palette.dim, marginTop: 32 }}>
          idea &rarr; thought &rarr; execution
        </div>
      </div>
    </AbsoluteFill>
  );
}
