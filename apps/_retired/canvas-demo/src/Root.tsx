import { Composition } from 'remotion';
import { Main, type MainProps } from './Main';

const defaultProps: MainProps = {
  targetLabel: 'acme-saas.local',
  pullPrompt: 'Make the hero green and the CTA say "Get started free"',
  outputFile: 'acme-saas.local.html',
};

export function Root() {
  return (
    <Composition
      id="Main"
      component={Main}
      durationInFrames={900}
      fps={30}
      width={1920}
      height={1080}
      defaultProps={defaultProps}
    />
  );
}
