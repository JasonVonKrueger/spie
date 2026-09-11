import { z } from 'zod';

import { formatAllowedCrudTables, isAllowedCrudTable } from './allowed-crud-tables.js';
import { findSimilarScriptIncludeFunctions } from './script-include-recommendations.js';

export function registerUpdateRecordTool(server, executeTool) {
  server.tool(
    'update_record',
    'Update a record in an allowed ServiceNow table by sys_id.',
    {
      table: z.string().trim().min(1),
      sysId: z.string().trim().min(1),
      fields: z.record(z.string(), z.unknown()).refine((value) => Object.keys(value).length > 0, {
        message: 'fields must include at least one field to update on the record'
      }),
      requestedFunctionNames: z.array(z.string().trim().min(1)).optional()
    },
    async (args) => {
      if (!isAllowedCrudTable(args.table)) {
        return {
          isError: true,
          content: [
            {
              type: 'text',
              text: `Updating records on table "${args.table}" is not allowed. Allowed tables: ${formatAllowedCrudTables()}.`
            }
          ]
        };
      }

      return executeTool(async (client) => {
        if (args.table === 'sys_script_include' && args.fields.script) {
          const similarFunctions = await findSimilarScriptIncludeFunctions(client, args.fields, {
            requestedFunctionNames: args.requestedFunctionNames,
            excludeSysIds: [args.sysId]
          });

          if (similarFunctions) {
            return {
              isError: true,
              table: args.table,
              sysId: args.sysId,
              displayText: similarFunctions.displayText,
              similarFunctions
            };
          }
        }

        return {
          table: args.table,
          sysId: args.sysId,
          result: await client.updateTableRecord({
            table: args.table,
            sysId: args.sysId,
            fields: args.fields
          })
        };
      });
    }
  );
}