import { z } from 'zod';

export function registerQueryTableRecordsTool(server, executeTool) {
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
}