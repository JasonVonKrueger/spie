import { z } from 'zod';

import { analyzeSyslogRecords, formatSyslogAnalysis } from './syslog-analysis.js';
import { DateInputError, MAX_SYSLOG_RANGE_DAYS, resolveSyslogDateRange } from './syslog-date-range.js';

const PAGE_SIZE = 500;
const MAX_RECORDS = 5000;
const SYSLOG_FIELDS = ['sys_created_on', 'level', 'source', 'message'];

function textResult(text, isError = false) {
  return { ...(isError ? { isError: true } : {}), content: [{ type: 'text', text }] };
}

// Warnings (1) and errors (2) in the range, newest first. sys_id is a tie-breaker so paging is stable.
function buildSyslogQuery(range) {
  return [
    `sys_created_on>=${range.startDateTime}`,
    `sys_created_on<=${range.endDateTime}`,
    'level=1^ORlevel=2',
    'ORDERBYDESCsys_created_on',
    'ORDERBYDESCsys_id'
  ].join('^');
}

// Read-only by construction: this tool only ever calls client.queryTableRecords against the syslog
// table. The table is fixed (not an argument), and syslog is not in ALLOWED_CRUD_TABLES.
async function fetchSyslogRecords(client, range) {
  const query = buildSyslogQuery(range);
  const records = [];
  let truncated = false;

  while (records.length < MAX_RECORDS) {
    const page = await client.queryTableRecords({
      table: 'syslog',
      query,
      fields: SYSLOG_FIELDS,
      limit: Math.min(PAGE_SIZE, MAX_RECORDS - records.length),
      offset: records.length
    });

    records.push(...page);

    if (page.length < PAGE_SIZE) {
      return { records, truncated };
    }
  }

  truncated = true;
  return { records, truncated };
}

export function registerAnalyzeSyslogTool(server, executeTool, options = {}) {
  server.tool(
    'analyze_syslog',
    `Analyze ServiceNow syslog (warning and error) records between a start date and an end date to find potential platform problems. Read-only: it never creates, updates, or deletes syslog records. If the user has not given both dates, ask them for a start date and an end date before calling. Dates can be written naturally (for example "09/23/2026" or "Sept 23, 2026"); if no year is given, the current year is assumed. The range is inclusive, interpreted in UTC, and cannot exceed ${MAX_SYSLOG_RANGE_DAYS} days (2 weeks).`,
    {
      startDate: z.string().trim().optional().describe('First day to analyze, e.g. "09/23/2026" or "Sept 23"'),
      endDate: z.string().trim().optional().describe('Last day to analyze (inclusive), e.g. "10/01/2026" or "Oct 1"')
    },
    async (args) => {
      if (!args.startDate || !args.endDate) {
        const missing = [!args.startDate && 'start date', !args.endDate && 'end date'].filter(Boolean).join(' and ');
        return textResult(
          `Please provide the ${missing} for the syslog analysis. Dates can be entered naturally, such as "09/23/2026" or "Sept 23, 2026" (the current year is assumed if omitted). The range can be at most ${MAX_SYSLOG_RANGE_DAYS} days (2 weeks).`
        );
      }

      let range;
      try {
        range = resolveSyslogDateRange(args.startDate, args.endDate, options.now?.() ?? new Date());
      } catch (error) {
        if (error instanceof DateInputError) {
          return textResult(error.message, true);
        }
        throw error;
      }

      return executeTool(async (client) => {
        const { records, truncated } = await fetchSyslogRecords(client, range);
        const analysis = analyzeSyslogRecords(records, range);

        return {
          table: 'syslog',
          range,
          truncated,
          analysis,
          displayText: formatSyslogAnalysis(analysis, range, { truncated, maxRecords: MAX_RECORDS })
        };
      });
    }
  );
}
