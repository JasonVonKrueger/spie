import { z } from 'zod';

import { ServiceNowApiError } from '../errors.js';
import { analyzeSyslogRecords, formatSyslogAnalysis } from './syslog-analysis.js';
import { DateInputError, MAX_SYSLOG_RANGE_DAYS, eachDay, resolveSyslogDateRange } from './syslog-date-range.js';

const PAGE_SIZE = 500;
// Each day is fetched separately with its own cap, so one noisy day cannot crowd out the others.
const MAX_RECORDS_PER_DAY = 1500;
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

async function fetchDayRecords(client, day) {
  const query = buildSyslogQuery({ startDateTime: `${day} 00:00:00`, endDateTime: `${day} 23:59:59` });
  const records = [];

  while (records.length < MAX_RECORDS_PER_DAY) {
    const page = await client.queryTableRecords({
      table: 'syslog',
      query,
      fields: SYSLOG_FIELDS,
      limit: Math.min(PAGE_SIZE, MAX_RECORDS_PER_DAY - records.length),
      offset: records.length
    });

    records.push(...page);

    if (page.length < PAGE_SIZE) {
      return { records, truncated: false };
    }
  }

  return { records, truncated: true };
}

// Read-only by construction: this tool only ever calls client.queryTableRecords against the syslog
// table. The table is fixed (not an argument), and syslog is not in ALLOWED_CRUD_TABLES.
export async function fetchSyslogRecords(client, range) {
  const records = [];
  const truncatedDays = [];

  try {
    for (const day of eachDay(range.startDate, range.endDate)) {
      const result = await fetchDayRecords(client, day);
      records.push(...result.records);
      if (result.truncated) {
        truncatedDays.push(day);
      }
    }
  } catch (error) {
    if (error instanceof ServiceNowApiError && error.status === 403) {
      throw new ServiceNowApiError(
        `Access to the syslog table was denied (403). The signed-in user needs read access to syslog and, if you use an OAuth integration, its Auth scope must include the Table API. ${error.message}`,
        403,
        error.details
      );
    }

    throw error;
  }

  return { records, truncatedDays };
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
        const { records, truncatedDays } = await fetchSyslogRecords(client, range);
        const analysis = analyzeSyslogRecords(records, range);

        return {
          table: 'syslog',
          range,
          truncatedDays,
          analysis,
          displayText: formatSyslogAnalysis(analysis, range, {
            truncatedDays,
            maxRecordsPerDay: MAX_RECORDS_PER_DAY
          })
        };
      });
    }
  );
}
