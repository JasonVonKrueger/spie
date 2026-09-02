import { z } from 'zod';

export function registerGetRecordBySysIdTool(server, executeTool) {
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