import { createProxyHandlers } from "../../../../lib/proxy";

export const { GET, POST, PUT, DELETE, PATCH } =
  createProxyHandlers("http://localhost:3001");
