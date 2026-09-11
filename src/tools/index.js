import { toToolErrorResult } from '../errors.js';
import { createServiceNowRuntime } from '../runtime.js';

import { registerCreateRecordTool } from './create-record.js';
import { registerGetRecordBySysIdTool } from './get-record-by-sys-id.js';
import { toSuccessResult } from './results.js';
import { registerQueryTableRecordsTool } from './query-table-records.js';
import { registerUpdateRecordTool } from './update-record.js';

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

  registerQueryTableRecordsTool(server, executeTool);
  registerGetRecordBySysIdTool(server, executeTool);
  registerCreateRecordTool(server, executeTool);
  registerUpdateRecordTool(server, executeTool);
}
