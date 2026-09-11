import { z } from 'zod';

import { formatAllowedCrudTables, isAllowedCrudTable } from './allowed-crud-tables.js';
import { findSimilarScriptIncludeFunctions } from './script-include-recommendations.js';

export function registerCreateRecordTool(server, executeTool) {
  server.tool(
    'create_record',
    'Create a record in an allowed ServiceNow table.',
    {
      table: z.string().trim().min(1),
      fields: z.record(z.string(), z.unknown()).refine((value) => Object.keys(value).length > 0, {
        message: 'fields must include at least one field to set on the new record'
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
              text: `Creating records on table "${args.table}" is not allowed. Allowed tables: ${formatAllowedCrudTables()}.`
            }
          ]
        };
      }

      return executeTool(async (client) => {
        if (args.table === 'sys_script_include') {
          const similarFunctions = await findSimilarScriptIncludeFunctions(client, args.fields, {
            requestedFunctionNames: args.requestedFunctionNames
          });

          if (similarFunctions) {
            return {
              isError: true,
              table: args.table,
              displayText: similarFunctions.displayText,
              similarFunctions
            };
          }
        }

        return {
          table: args.table,
          result: await client.createTableRecord({
            table: args.table,
            fields: args.fields
          })
        };
      });
    }
  );
}