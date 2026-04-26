import { z } from 'zod';

export const layerSchema = z.enum(['ui', 'api', 'ext', 'lib', 'state']);

export const fetchSchema = z.object({
  method: z.string(),
  url: z.string(),
  status: z.number().int().optional(),
  contentType: z.string().optional(),
  ts: z.number().int().optional(),
});

export const boundsSchema = z.object({
  x: z.number(),
  y: z.number(),
  w: z.number(),
  h: z.number(),
});

export const regionSchema = z.object({
  id: z.string(),
  n: z.number().int(),
  name: z.string(),
  layer: layerSchema,
  selector: z.string().optional(),
  file: z.string().optional(),
  line: z.number().int().optional(),
  detection: z.string().optional(),
  desc: z.string().optional(),
  note: z.string().optional(),
  kind: z.string().optional(),
  bounds: boundsSchema.optional(),
  fetches: z.array(fetchSchema).optional(),
});

export const chainNodeSchema = z.object({
  n: z.number().int(),
  layer: layerSchema,
  label: z.string(),
  detail: z.string().optional(),
  probe: z.record(z.string(), z.unknown()).optional(),
  file: z.string().optional(),
  line: z.number().int().optional(),
});

export const chainSchema = z.object({
  id: z.string(),
  nodes: z.array(chainNodeSchema).min(1),
});

export const layerInfoSchema = z.object({
  color: z.string(),
});

export const layersTaxonomySchema = z
  .object({
    ui: layerInfoSchema,
    api: layerInfoSchema,
    ext: layerInfoSchema,
    lib: layerInfoSchema,
    state: layerInfoSchema,
  })
  .catchall(layerInfoSchema);

export const metadataSchema = z.object({
  target: z.string(),
  mode: z.enum(['spa', 'mpa', 'extension']),
  source: z.string().optional(),
  timestamp: z.string(),
  tools: z.array(z.string()).min(1),
});

export const anatomyV1Schema = z.object({
  version: z.literal('anatomy-v1'),
  metadata: metadataSchema,
  regions: z.array(regionSchema),
  chains: z.array(chainSchema),
  layers: layersTaxonomySchema,
});

export type AnatomyV1 = z.infer<typeof anatomyV1Schema>;
export type Region = z.infer<typeof regionSchema>;
export type Chain = z.infer<typeof chainSchema>;
export type ChainNode = z.infer<typeof chainNodeSchema>;
export type Fetch = z.infer<typeof fetchSchema>;
export type Bounds = z.infer<typeof boundsSchema>;
export type Layer = z.infer<typeof layerSchema>;
export type Metadata = z.infer<typeof metadataSchema>;
