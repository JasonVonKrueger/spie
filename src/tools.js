import { z } from 'zod';

import { toToolErrorResult } from './errors.js';
import { createServiceNowRuntime } from './runtime.js';

function toSuccessResult(payload) {
  return {
    content: [
      {
        type: 'text',
        text: JSON.stringify(payload, null, 2)
      }
    ],
    structuredContent: payload
  };
}

export function registerServiceNowTools(server, options = {}) {
  const runtime = options.runtime ?? createServiceNowRuntime();

  async function executeTool(operation) {
    try {
      const payload = await runtime.execute(operation);
      return toSuccessResult(payload);
    } catch (error) {
      return toToolErrorResult(error);
    }
  }

  server.tool(
    'query_table_records',
    'Query records from a ServiceNow table.',
    {
      table: z.string().trim().min(1),
      query: z.string().trim().optional(),
      fields: z.array(z.string().trim().min(1)).optional(),
      limit: z.number().int().min(1).max(100).optional(),
      offset: z.number().int().min(0).optional()
    },
    async (args) =>
      executeTool(async (client) => ({
        table: args.table,
        query: args.query ?? null,
        offset: args.offset ?? 0,
        limit: args.limit ?? 10,
        result: await client.queryTableRecords({
          table: args.table,
          query: args.query,
          fields: args.fields,
          limit: args.limit ?? 10,
          offset: args.offset ?? 0
        })
      }))
  );

  server.tool(
    'get_record_by_sys_id',
    'Fetch a single ServiceNow table record by sys_id.',
    {
      table: z.string().trim().min(1),
      sysId: z.string().trim().min(1),
      fields: z.array(z.string().trim().min(1)).optional()
    },
    async (args) =>
      executeTool(async (client) => ({
        table: args.table,
        sysId: args.sysId,
        result: await client.getRecordBySysId({
          table: args.table,
          sysId: args.sysId,
          fields: args.fields
        })
      }))
  );
}
