import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';

import { registerServiceNowTools } from './tools.js';

export function createServer(options = {}) {
  const server = new McpServer({
    name: 'servicenow-mcp-server',
    version: '1.0.0'
  });

  registerServiceNowTools(server, options);

  return server;
}
